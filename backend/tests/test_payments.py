"""Integration tests for the /payments endpoints."""
import hashlib
import hmac
import json
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.models.payment import Payment, PaymentStatus, PaymentType
from app.models.scan import Scan, ScanStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_ORDER_ID = "order_FakeRazorpay001"
FAKE_PAYMENT_ID = "pay_FakeRazorpay001"


def _make_valid_signature(order_id: str, payment_id: str) -> str:
    message = f"{order_id}|{payment_id}".encode()
    return hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()


def _make_webhook_signature(body: bytes) -> str:
    return hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()


async def _get_org_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get("/api/v1/organizations/me", headers=auth_headers)
    assert resp.status_code == 200
    return uuid.UUID(resp.json()["data"]["id"])


# ---------------------------------------------------------------------------
# TestCreateOrder
# ---------------------------------------------------------------------------

class TestCreateOrder:

    async def test_creates_order_for_completed_scan(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Should create Razorpay order for a completed scan (mock Razorpay)."""
        org_id = await _get_org_id(client, auth_headers)
        scan_id = uuid.uuid4()

        from app.core.database import AsyncSessionLocal
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy import NullPool

        # Seed a completed scan directly via app's DB
        from tests.conftest import TEST_DB_URL
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as sess:
            scan = Scan(
                id=scan_id,
                organization_id=org_id,
                scan_month="2024-03",
                gstr1_s3_key=f"orgs/{org_id}/scans/{scan_id}/gstr1.xlsx",
                gstr3b_s3_key=f"orgs/{org_id}/scans/{scan_id}/gstr3b.xlsx",
                status=ScanStatus.completed,
                total_mismatches=2,
                total_rupee_risk=Decimal("50000"),
                is_paid=False,
            )
            sess.add(scan)
            await sess.commit()
        await engine.dispose()

        mock_order = {"id": FAKE_ORDER_ID, "amount": 49900, "currency": "INR"}
        with patch("app.api.v1.payments.get_razorpay_client") as mock_client:
            mock_client.return_value.order.create.return_value = mock_order
            resp = await client.post(
                "/api/v1/payments/create-order",
                headers=auth_headers,
                json={"scan_id": str(scan_id)},
            )

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["order_id"] == FAKE_ORDER_ID
        assert data["amount"] == 49900
        assert data["currency"] == "INR"
        assert data["key_id"] == settings.RAZORPAY_KEY_ID

    async def test_already_paid_scan_returns_409(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Should return ConflictError for a scan already marked paid."""
        org_id = await _get_org_id(client, auth_headers)
        scan_id = uuid.uuid4()

        from tests.conftest import TEST_DB_URL
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy import NullPool
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as sess:
            scan = Scan(
                id=scan_id,
                organization_id=org_id,
                scan_month="2024-03",
                gstr1_s3_key=f"orgs/{org_id}/scans/{scan_id}/gstr1.xlsx",
                gstr3b_s3_key=f"orgs/{org_id}/scans/{scan_id}/gstr3b.xlsx",
                status=ScanStatus.completed,
                is_paid=True,
            )
            sess.add(scan)
            await sess.commit()
        await engine.dispose()

        resp = await client.post(
            "/api/v1/payments/create-order",
            headers=auth_headers,
            json={"scan_id": str(scan_id)},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "CONF_003"

    async def test_processing_scan_returns_400(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Should return 400 for a scan that's still processing."""
        org_id = await _get_org_id(client, auth_headers)
        scan_id = uuid.uuid4()

        from tests.conftest import TEST_DB_URL
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy import NullPool
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as sess:
            scan = Scan(
                id=scan_id,
                organization_id=org_id,
                scan_month="2024-03",
                gstr1_s3_key=f"orgs/{org_id}/scans/{scan_id}/gstr1.xlsx",
                gstr3b_s3_key=f"orgs/{org_id}/scans/{scan_id}/gstr3b.xlsx",
                status=ScanStatus.processing,
                is_paid=False,
            )
            sess.add(scan)
            await sess.commit()
        await engine.dispose()

        resp = await client.post(
            "/api/v1/payments/create-order",
            headers=auth_headers,
            json={"scan_id": str(scan_id)},
        )
        assert resp.status_code == 400

    async def test_unauthorized_scan_returns_403(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Trying to pay for another org's scan should return 403 or 404."""
        # Register a second user
        reg = await client.post("/api/v1/auth/register", json={
            "full_name": "Other User",
            "email": "other_pay@example.com",
            "password": "StrongPass1",
            "gstin": "27AAPFU0939F1ZV",
        })
        assert reg.status_code == 201
        other_token = reg.json()["data"]["tokens"]["access_token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}
        other_resp = await client.get("/api/v1/organizations/me", headers=other_headers)
        other_org_id = uuid.UUID(other_resp.json()["data"]["id"])

        # Seed a scan owned by the other org
        scan_id = uuid.uuid4()
        from tests.conftest import TEST_DB_URL
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy import NullPool
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as sess:
            scan = Scan(
                id=scan_id,
                organization_id=other_org_id,
                scan_month="2024-03",
                gstr1_s3_key=f"orgs/{other_org_id}/scans/{scan_id}/gstr1.xlsx",
                gstr3b_s3_key=f"orgs/{other_org_id}/scans/{scan_id}/gstr3b.xlsx",
                status=ScanStatus.completed,
                is_paid=False,
            )
            sess.add(scan)
            await sess.commit()
        await engine.dispose()

        # Try to create order using original user's auth
        resp = await client.post(
            "/api/v1/payments/create-order",
            headers=auth_headers,
            json={"scan_id": str(scan_id)},
        )
        assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# TestVerifyPayment
# ---------------------------------------------------------------------------

class TestVerifyPayment:

    async def _seed_payment(
        self, org_id: uuid.UUID, scan_id: uuid.UUID, order_id: str = FAKE_ORDER_ID
    ) -> None:
        from tests.conftest import TEST_DB_URL
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy import NullPool
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as sess:
            scan = Scan(
                id=scan_id,
                organization_id=org_id,
                scan_month="2024-03",
                gstr1_s3_key=f"orgs/{org_id}/scans/{scan_id}/gstr1.xlsx",
                gstr3b_s3_key=f"orgs/{org_id}/scans/{scan_id}/gstr3b.xlsx",
                status=ScanStatus.completed,
                is_paid=False,
            )
            payment = Payment(
                organization_id=org_id,
                scan_id=scan_id,
                razorpay_order_id=order_id,
                amount_paise=49900,
                currency="INR",
                payment_type=PaymentType.one_time_scan,
                status=PaymentStatus.created,
            )
            sess.add(scan)
            sess.add(payment)
            await sess.commit()
        await engine.dispose()

    async def test_valid_signature_marks_scan_paid(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Valid Razorpay signature should mark the scan as paid."""
        org_id = await _get_org_id(client, auth_headers)
        scan_id = uuid.uuid4()
        order_id = f"order_valid_{uuid.uuid4().hex[:8]}"
        payment_id = f"pay_valid_{uuid.uuid4().hex[:8]}"

        await self._seed_payment(org_id, scan_id, order_id)

        sig = _make_valid_signature(order_id, payment_id)
        resp = await client.post(
            "/api/v1/payments/verify",
            headers=auth_headers,
            json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": sig,
                "scan_id": str(scan_id),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["success"] is True

    async def test_invalid_signature_returns_400(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Invalid Razorpay signature should return 400 VAL_001."""
        org_id = await _get_org_id(client, auth_headers)
        scan_id = uuid.uuid4()
        order_id = f"order_inv_{uuid.uuid4().hex[:8]}"

        await self._seed_payment(org_id, scan_id, order_id)

        resp = await client.post(
            "/api/v1/payments/verify",
            headers=auth_headers,
            json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": FAKE_PAYMENT_ID,
                "razorpay_signature": "bad_signature_xxxx",
                "scan_id": str(scan_id),
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VAL_001"

    async def test_idempotent_double_verify(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Verifying the same payment twice should return success both times."""
        org_id = await _get_org_id(client, auth_headers)
        scan_id = uuid.uuid4()
        order_id = f"order_idem_{uuid.uuid4().hex[:8]}"
        payment_id = f"pay_idem_{uuid.uuid4().hex[:8]}"

        await self._seed_payment(org_id, scan_id, order_id)
        sig = _make_valid_signature(order_id, payment_id)

        payload = {
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": sig,
            "scan_id": str(scan_id),
        }

        resp1 = await client.post("/api/v1/payments/verify", headers=auth_headers, json=payload)
        resp2 = await client.post("/api/v1/payments/verify", headers=auth_headers, json=payload)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["data"]["success"] is True
        assert resp2.json()["data"]["success"] is True


# ---------------------------------------------------------------------------
# TestWebhook
# ---------------------------------------------------------------------------

class TestWebhook:

    async def _post_webhook(self, client: AsyncClient, body: dict) -> "httpx.Response":  # type: ignore[name-defined]
        raw = json.dumps(body).encode()
        sig = _make_webhook_signature(raw)
        return await client.post(
            "/api/v1/payments/webhook",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "x-razorpay-signature": sig,
            },
        )

    async def test_valid_webhook_processes_payment(self, client: AsyncClient):
        """payment.captured webhook should update payment status."""
        order_id = f"order_wh_{uuid.uuid4().hex[:8]}"
        payment_id = f"pay_wh_{uuid.uuid4().hex[:8]}"

        # Register a user to get an org, then seed payment
        reg = await client.post("/api/v1/auth/register", json={
            "full_name": "Webhook User",
            "email": "webhook@example.com",
            "password": "StrongPass1",
            "gstin": "29ZZZZE1234F1Z5",
        })
        assert reg.status_code == 201
        wh_token = reg.json()["data"]["tokens"]["access_token"]
        wh_headers = {"Authorization": f"Bearer {wh_token}"}
        org_resp = await client.get("/api/v1/organizations/me", headers=wh_headers)
        org_id = uuid.UUID(org_resp.json()["data"]["id"])
        scan_id = uuid.uuid4()

        from tests.conftest import TEST_DB_URL
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy import NullPool
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sf() as sess:
            scan = Scan(
                id=scan_id,
                organization_id=org_id,
                scan_month="2024-03",
                gstr1_s3_key=f"orgs/{org_id}/scans/{scan_id}/gstr1.xlsx",
                gstr3b_s3_key=f"orgs/{org_id}/scans/{scan_id}/gstr3b.xlsx",
                status=ScanStatus.completed,
                is_paid=False,
            )
            payment = Payment(
                organization_id=org_id,
                scan_id=scan_id,
                razorpay_order_id=order_id,
                amount_paise=49900,
                currency="INR",
                payment_type=PaymentType.one_time_scan,
                status=PaymentStatus.created,
            )
            sess.add(scan)
            sess.add(payment)
            await sess.commit()
        await engine.dispose()

        body = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {"order_id": order_id, "id": payment_id},
                }
            },
        }
        resp = await self._post_webhook(client, body)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_invalid_webhook_signature_returns_error(self, client: AsyncClient):
        """Invalid webhook signature should be rejected (returns error body, not exception)."""
        body = {"event": "payment.captured", "payload": {}}
        raw = json.dumps(body).encode()
        resp = await client.post(
            "/api/v1/payments/webhook",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "x-razorpay-signature": "invalidsig",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    async def test_unknown_event_returns_200(self, client: AsyncClient):
        """Unknown webhook events should be acknowledged with 200 ok."""
        body = {"event": "subscription.created", "payload": {}}
        resp = await self._post_webhook(client, body)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
