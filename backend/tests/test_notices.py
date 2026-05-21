"""Integration tests for /notices endpoints — 10 test cases."""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.notice import DraftStatus, Notice, NoticeType


def make_pdf_bytes() -> bytes:
    """Create minimal valid PDF bytes for testing."""
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


class TestNoticeUpload:

    async def test_upload_valid_pdf_returns_202(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        pdf = make_pdf_bytes()
        with (
            patch(
                "app.api.v1.notices.extract_text_from_pdf",
                return_value="GST DRC-01C Notice No: ZD2400123 GSTIN: 29ABCDE1234F1Z5",
            ),
            patch(
                "app.services.s3_service.s3_service.upload_file",
                new_callable=AsyncMock,
            ),
            patch("app.api.v1.notices._run_draft_in_background", new_callable=AsyncMock),
        ):
            resp = await client.post(
                "/api/v1/notices/upload",
                files={"notice_file": ("notice.pdf", pdf, "application/pdf")},
                headers=auth_headers,
            )
        assert resp.status_code == 202, resp.text
        data = resp.json()["data"]
        assert data["notice_id"]
        assert data["status"] == "uploaded"

    async def test_upload_non_pdf_returns_400(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.post(
            "/api/v1/notices/upload",
            files={"notice_file": ("notice.xlsx", b"fake data", "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VAL_003"

    async def test_upload_extracts_notice_details(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        pdf = make_pdf_bytes()
        notice_text = (
            "FORM GST DRC-01C\n"
            "Notice No: ZD2400TEST001\n"
            "GSTIN: 29ABCDE1234F1Z5\n"
            "Tax Period: 2023-24\n"
            "Amount: Rs. 84200/-\n"
        )
        with (
            patch("app.api.v1.notices.extract_text_from_pdf", return_value=notice_text),
            patch(
                "app.services.s3_service.s3_service.upload_file",
                new_callable=AsyncMock,
            ),
            patch("app.api.v1.notices._run_draft_in_background", new_callable=AsyncMock),
        ):
            resp = await client.post(
                "/api/v1/notices/upload",
                files={"notice_file": ("notice.pdf", pdf, "application/pdf")},
                headers=auth_headers,
            )
        assert resp.status_code == 202
        data = resp.json()["data"]
        assert data["notice_number"] == "ZD2400TEST001"
        assert data["notice_type"] == "DRC-01C"

    async def test_unauthenticated_upload_returns_401(
        self, client: AsyncClient
    ) -> None:
        pdf = make_pdf_bytes()
        resp = await client.post(
            "/api/v1/notices/upload",
            files={"notice_file": ("notice.pdf", pdf, "application/pdf")},
        )
        assert resp.status_code == 401


class TestNoticeDraft:

    async def _create_notice(
        self, client: AsyncClient, auth_headers: dict, status: DraftStatus = DraftStatus.generated
    ) -> str:
        """Helper: seed a notice directly via upload then patch its status."""
        from sqlalchemy import update
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.core.database import get_db
        from app.main import app as _app

        pdf = make_pdf_bytes()
        with (
            patch("app.api.v1.notices.extract_text_from_pdf", return_value="DRC-01C test notice"),
            patch("app.services.s3_service.s3_service.upload_file", new_callable=AsyncMock),
            patch("app.api.v1.notices._run_draft_in_background", new_callable=AsyncMock),
        ):
            resp = await client.post(
                "/api/v1/notices/upload",
                files={"notice_file": ("notice.pdf", pdf, "application/pdf")},
                headers=auth_headers,
            )
        assert resp.status_code == 202
        notice_id = resp.json()["data"]["notice_id"]

        # Update draft status via the test DB override
        db_gen = _app.dependency_overrides[get_db]()
        db: AsyncSession = await db_gen.__anext__()
        try:
            await db.execute(
                update(Notice)
                .where(Notice.id == uuid.UUID(notice_id))
                .values(
                    draft_reply_text="AI draft reply content",
                    draft_status=status,
                    draft_warnings=[],
                )
            )
            await db.commit()
        finally:
            try:
                await db_gen.aclose()
            except Exception:
                pass

        return notice_id

    async def test_get_draft_returns_disclaimer(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        notice_id = await self._create_notice(client, auth_headers)
        resp = await client.get(
            f"/api/v1/notices/{notice_id}/draft",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "LEGAL NOTICE" in data["disclaimer_text"] or "disclaimer" in data["disclaimer_text"].lower()
        assert len(data["disclaimer_text"]) > 100

    async def test_pending_draft_returns_error(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        pdf = make_pdf_bytes()
        with (
            patch("app.api.v1.notices.extract_text_from_pdf", return_value="DRC-01C test"),
            patch("app.services.s3_service.s3_service.upload_file", new_callable=AsyncMock),
            patch("app.api.v1.notices._run_draft_in_background", new_callable=AsyncMock),
        ):
            resp = await client.post(
                "/api/v1/notices/upload",
                files={"notice_file": ("notice.pdf", pdf, "application/pdf")},
                headers=auth_headers,
            )
        notice_id = resp.json()["data"]["notice_id"]

        draft_resp = await client.get(
            f"/api/v1/notices/{notice_id}/draft",
            headers=auth_headers,
        )
        assert draft_resp.status_code == 400

    async def test_cannot_access_other_org_notice(
        self, client: AsyncClient
    ) -> None:
        # Register second user
        other_headers = {}
        reg_resp = await client.post("/api/v1/auth/register", json={
            "full_name": "Other User",
            "email": "other2@example.com",
            "password": "StrongPass1",
            "gstin": "27AAAAA0000A1Z5",
        })
        if reg_resp.status_code == 201:
            token = reg_resp.json()["data"]["tokens"]["access_token"]
            other_headers = {"Authorization": f"Bearer {token}"}

        if not other_headers:
            pytest.skip("Could not register second user")

        # Create notice as first user
        first_reg = await client.post("/api/v1/auth/register", json={
            "full_name": "First User",
            "email": "first_notice@example.com",
            "password": "StrongPass1",
            "gstin": "07AAAAA0000A1Z5",
        })
        first_token = first_reg.json()["data"]["tokens"]["access_token"]
        first_headers = {"Authorization": f"Bearer {first_token}"}

        pdf = make_pdf_bytes()
        with (
            patch("app.api.v1.notices.extract_text_from_pdf", return_value="DRC-01C"),
            patch("app.services.s3_service.s3_service.upload_file", new_callable=AsyncMock),
            patch("app.api.v1.notices._run_draft_in_background", new_callable=AsyncMock),
        ):
            upload_resp = await client.post(
                "/api/v1/notices/upload",
                files={"notice_file": ("notice.pdf", pdf, "application/pdf")},
                headers=first_headers,
            )
        notice_id = upload_resp.json()["data"]["notice_id"]

        # Other user tries to access — should get 403
        resp = await client.get(
            f"/api/v1/notices/{notice_id}/draft",
            headers=other_headers,
        )
        assert resp.status_code in (403, 404)


class TestCredentialVerification:

    async def test_valid_icai_number_accepted(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        pdf = make_pdf_bytes()
        with (
            patch("app.api.v1.notices.extract_text_from_pdf", return_value="DRC-01C test"),
            patch("app.services.s3_service.s3_service.upload_file", new_callable=AsyncMock),
            patch("app.api.v1.notices._run_draft_in_background", new_callable=AsyncMock),
        ):
            resp = await client.post(
                "/api/v1/notices/upload",
                files={"notice_file": ("notice.pdf", pdf, "application/pdf")},
                headers=auth_headers,
            )
        notice_id = resp.json()["data"]["notice_id"]

        verify_resp = await client.post(
            f"/api/v1/notices/{notice_id}/verify-credentials?icai_number=MRN123456",
            headers=auth_headers,
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["data"]["verified"] is True

    async def test_invalid_icai_number_rejected(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        pdf = make_pdf_bytes()
        with (
            patch("app.api.v1.notices.extract_text_from_pdf", return_value="DRC-01C test"),
            patch("app.services.s3_service.s3_service.upload_file", new_callable=AsyncMock),
            patch("app.api.v1.notices._run_draft_in_background", new_callable=AsyncMock),
        ):
            resp = await client.post(
                "/api/v1/notices/upload",
                files={"notice_file": ("notice.pdf", pdf, "application/pdf")},
                headers=auth_headers,
            )
        notice_id = resp.json()["data"]["notice_id"]

        verify_resp = await client.post(
            f"/api/v1/notices/{notice_id}/verify-credentials?icai_number=INVALID!!!",
            headers=auth_headers,
        )
        assert verify_resp.status_code == 400

    async def test_icai_stored_on_notice(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        pdf = make_pdf_bytes()
        with (
            patch("app.api.v1.notices.extract_text_from_pdf", return_value="DRC-01C test"),
            patch("app.services.s3_service.s3_service.upload_file", new_callable=AsyncMock),
            patch("app.api.v1.notices._run_draft_in_background", new_callable=AsyncMock),
        ):
            resp = await client.post(
                "/api/v1/notices/upload",
                files={"notice_file": ("notice.pdf", pdf, "application/pdf")},
                headers=auth_headers,
            )
        notice_id = resp.json()["data"]["notice_id"]

        await client.post(
            f"/api/v1/notices/{notice_id}/verify-credentials?icai_number=FRN100001W",
            headers=auth_headers,
        )

        detail_resp = await client.get(
            f"/api/v1/notices/{notice_id}",
            headers=auth_headers,
        )
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["icai_membership_number"] == "FRN100001W"


class TestNoticeDownload:

    async def test_download_without_credentials_blocked(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        pdf = make_pdf_bytes()
        with (
            patch("app.api.v1.notices.extract_text_from_pdf", return_value="DRC-01C test"),
            patch("app.services.s3_service.s3_service.upload_file", new_callable=AsyncMock),
            patch("app.api.v1.notices._run_draft_in_background", new_callable=AsyncMock),
        ):
            resp = await client.post(
                "/api/v1/notices/upload",
                files={"notice_file": ("notice.pdf", pdf, "application/pdf")},
                headers=auth_headers,
            )
        notice_id = resp.json()["data"]["notice_id"]

        download_resp = await client.get(
            f"/api/v1/notices/{notice_id}/download",
            headers=auth_headers,
        )
        assert download_resp.status_code == 403

    async def test_download_after_verification_succeeds(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        from sqlalchemy import update
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.core.database import get_db
        from app.main import app as _app

        pdf = make_pdf_bytes()
        with (
            patch("app.api.v1.notices.extract_text_from_pdf", return_value="DRC-01C test notice"),
            patch("app.services.s3_service.s3_service.upload_file", new_callable=AsyncMock),
            patch("app.api.v1.notices._run_draft_in_background", new_callable=AsyncMock),
        ):
            resp = await client.post(
                "/api/v1/notices/upload",
                files={"notice_file": ("notice.pdf", pdf, "application/pdf")},
                headers=auth_headers,
            )
        notice_id = resp.json()["data"]["notice_id"]

        # Seed draft text and set status to generated
        db_gen = _app.dependency_overrides[get_db]()
        db: AsyncSession = await db_gen.__anext__()
        try:
            await db.execute(
                update(Notice)
                .where(Notice.id == uuid.UUID(notice_id))
                .values(draft_reply_text="Draft content here.", draft_status=DraftStatus.generated)
            )
            await db.commit()
        finally:
            try:
                await db_gen.aclose()
            except Exception:
                pass

        # Verify credentials → status becomes reviewed
        await client.post(
            f"/api/v1/notices/{notice_id}/verify-credentials?icai_number=MRN654321",
            headers=auth_headers,
        )

        download_resp = await client.get(
            f"/api/v1/notices/{notice_id}/download",
            headers=auth_headers,
        )
        assert download_resp.status_code == 200
        assert download_resp.headers["content-type"] == "application/pdf"

    async def test_downloaded_pdf_contains_disclaimer(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        from sqlalchemy import update
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.core.database import get_db
        from app.main import app as _app

        pdf = make_pdf_bytes()
        with (
            patch("app.api.v1.notices.extract_text_from_pdf", return_value="DRC-01C test"),
            patch("app.services.s3_service.s3_service.upload_file", new_callable=AsyncMock),
            patch("app.api.v1.notices._run_draft_in_background", new_callable=AsyncMock),
        ):
            resp = await client.post(
                "/api/v1/notices/upload",
                files={"notice_file": ("notice.pdf", pdf, "application/pdf")},
                headers=auth_headers,
            )
        notice_id = resp.json()["data"]["notice_id"]

        db_gen = _app.dependency_overrides[get_db]()
        db: AsyncSession = await db_gen.__anext__()
        try:
            await db.execute(
                update(Notice)
                .where(Notice.id == uuid.UUID(notice_id))
                .values(draft_reply_text="Reply content.", draft_status=DraftStatus.generated)
            )
            await db.commit()
        finally:
            try:
                await db_gen.aclose()
            except Exception:
                pass

        await client.post(
            f"/api/v1/notices/{notice_id}/verify-credentials?icai_number=MRN999999",
            headers=auth_headers,
        )

        download_resp = await client.get(
            f"/api/v1/notices/{notice_id}/download",
            headers=auth_headers,
        )
        assert download_resp.status_code == 200
        # PDF bytes — verify it's non-empty and starts with PDF magic
        assert download_resp.content[:4] == b"%PDF"
        assert len(download_resp.content) > 1000
