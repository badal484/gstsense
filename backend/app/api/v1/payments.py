import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional

import razorpay
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org, get_current_user, get_db_session
from app.core.config import settings
from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.security import verify_razorpay_payment_signature
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.payment import Payment, PaymentStatus, PaymentType
from app.models.scan import Scan, ScanStatus
from app.models.user import User
from app.schemas.common import ApiResponse, make_response
from app.schemas.payment import (
    CreateOrderRequest,
    CreateOrderResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)
from app.services.referral_service import process_payment_commission

logger = get_logger(__name__)

router = APIRouter(prefix="/payments", tags=["Payments"])

ONE_TIME_SCAN_PRICE_PAISE = 49900
_IDEMPOTENCY_WINDOW_MINUTES = 30


def get_razorpay_client() -> razorpay.Client:
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@router.post(
    "/create-order",
    response_model=ApiResponse[CreateOrderResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Razorpay payment order",
)
async def create_order(
    request_body: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[CreateOrderResponse]:
    # 1. Fetch and validate scan
    result = await db.execute(select(Scan).where(Scan.id == request_body.scan_id))
    scan = result.scalar_one_or_none()
    if scan is None:
        raise NotFoundError.scan(str(request_body.scan_id))
    if scan.organization_id != org.id:
        raise AuthorizationError.resource_not_owned("scan")

    # 2. Scan must be completed
    if scan.status != ScanStatus.completed:
        raise ValidationError(
            message="Scan is still processing. Please wait until it completes.",
            code="VAL_005",
        )

    # 3. Already paid
    if scan.is_paid:
        raise ConflictError.payment_already_processed(str(request_body.scan_id))

    # 4. Idempotency — reuse recent pending payment
    existing_result = await db.execute(
        select(Payment).where(
            Payment.scan_id == request_body.scan_id,
            Payment.status == PaymentStatus.created,
        )
    )
    existing_payment = existing_result.scalar_one_or_none()
    if existing_payment is not None:
        window = timedelta(minutes=_IDEMPOTENCY_WINDOW_MINUTES)
        age = datetime.now(tz=timezone.utc) - existing_payment.created_at.replace(tzinfo=timezone.utc)
        if age < window:
            logger.info("reusing_existing_payment_order", order_id=existing_payment.razorpay_order_id)
            return make_response(CreateOrderResponse(
                order_id=existing_payment.razorpay_order_id,
                amount=existing_payment.amount_paise,
                amount_rupees=existing_payment.amount_rupees,
                currency=existing_payment.currency,
                key_id=settings.RAZORPAY_KEY_ID,
                scan_id=request_body.scan_id,
            ))

    # 5. Create Razorpay order
    try:
        client = get_razorpay_client()
        order = client.order.create({
            "amount": ONE_TIME_SCAN_PRICE_PAISE,
            "currency": "INR",
            "notes": {
                "scan_id": str(request_body.scan_id),
                "org_id": str(org.id),
                "gstin": org.gstin,
            },
        })
    except Exception as exc:
        logger.error("razorpay_order_create_failed", error=str(exc))
        raise ExternalServiceError.payment_service_error(str(exc))

    # 6. Persist Payment record
    payment = Payment(
        organization_id=org.id,
        scan_id=request_body.scan_id,
        razorpay_order_id=order["id"],
        amount_paise=ONE_TIME_SCAN_PRICE_PAISE,
        currency="INR",
        payment_type=PaymentType.one_time_scan,
        status=PaymentStatus.created,
    )
    db.add(payment)

    # 7. Audit log
    db.add(AuditLog(
        action="payment_order_created",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="payment",
        resource_id=payment.id,
        metadata_json={"razorpay_order_id": order["id"], "scan_id": str(request_body.scan_id)},
    ))

    await db.commit()
    logger.info("payment_order_created", order_id=order["id"], scan_id=str(request_body.scan_id))

    return make_response(CreateOrderResponse(
        order_id=order["id"],
        amount=ONE_TIME_SCAN_PRICE_PAISE,
        amount_rupees=payment.amount_rupees,
        currency="INR",
        key_id=settings.RAZORPAY_KEY_ID,
        scan_id=request_body.scan_id,
    ))


@router.post(
    "/verify",
    response_model=ApiResponse[VerifyPaymentResponse],
    status_code=status.HTTP_200_OK,
    summary="Verify Razorpay payment",
)
async def verify_payment(
    request_body: VerifyPaymentRequest,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[VerifyPaymentResponse]:
    # 1. Find payment by order ID
    result = await db.execute(
        select(Payment).where(Payment.razorpay_order_id == request_body.razorpay_order_id)
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise NotFoundError(
            message=f"Payment order '{request_body.razorpay_order_id}' not found",
            code="NF_001",
        )
    if payment.organization_id != org.id:
        raise AuthorizationError.resource_not_owned("payment")

    # 2. Ensure payload scan_id matches the order's scan_id.
    if payment.scan_id is None or payment.scan_id != request_body.scan_id:
        raise ValidationError(
            message="Payment order does not match the provided scan.",
            code="VAL_001",
        )

    # 3. Verify Razorpay signature
    valid = verify_razorpay_payment_signature(
        order_id=request_body.razorpay_order_id,
        payment_id=request_body.razorpay_payment_id,
        signature=request_body.razorpay_signature,
    )
    if not valid:
        raise ValidationError(
            message="Payment verification failed. Please contact support.",
            code="VAL_001",
        )

    # 4. Idempotent — already paid (only after signature validation)
    if payment.status == PaymentStatus.paid:
        return make_response(VerifyPaymentResponse(
            success=True,
            scan_id=request_body.scan_id,
            message="Payment already verified.",
        ))

    # 5. Update payment
    payment.status = PaymentStatus.paid
    payment.razorpay_payment_id = request_body.razorpay_payment_id

    # 6. Mark scan paid
    await db.execute(
        update(Scan)
        .where(Scan.id == request_body.scan_id)
        .values(is_paid=True)
    )

    # 7. Audit log
    db.add(AuditLog(
        action="payment_completed",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="payment",
        resource_id=payment.id,
        metadata_json={
            "razorpay_order_id": request_body.razorpay_order_id,
            "razorpay_payment_id": request_body.razorpay_payment_id,
            "scan_id": str(request_body.scan_id),
        },
    ))

    # 8. Process referral commission — fault-tolerant, never blocks payment
    try:
        await process_payment_commission(db, payment)
    except Exception as exc:
        logger.error(
            "commission_calculation_failed",
            payment_id=str(payment.id),
            error=str(exc),
        )

    await db.commit()
    logger.info(
        "payment_verified",
        order_id=request_body.razorpay_order_id,
        payment_id=request_body.razorpay_payment_id,
    )

    return make_response(VerifyPaymentResponse(
        success=True,
        scan_id=request_body.scan_id,
        message="Payment verified successfully. Report unlocked.",
    ))


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Razorpay webhook handler",
    description="Receives payment events from Razorpay",
)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    body_bytes = await request.body()

    # 2. Verify signature
    if not x_razorpay_signature:
        logger.warning("webhook_missing_signature")
        return {"status": "error", "message": "missing signature"}

    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, x_razorpay_signature):
        logger.warning("webhook_signature_invalid")
        return {"status": "error", "message": "invalid signature"}

    # 3. Parse body
    import json as _json
    try:
        payload = _json.loads(body_bytes)
    except Exception:
        return {"status": "ok"}

    event = payload.get("event", "")
    logger.info("webhook_received", webhook_event=event)

    # 4. Handle events
    if event == "payment.captured":
        try:
            order_id = payload["payload"]["payment"]["entity"]["order_id"]
            payment_id = payload["payload"]["payment"]["entity"]["id"]
        except (KeyError, TypeError):
            logger.warning("webhook_malformed_payload", webhook_event=event)
            return {"status": "ok"}

        result = await db.execute(
            select(Payment).where(Payment.razorpay_order_id == order_id)
        )
        payment = result.scalar_one_or_none()
        if payment is None:
            logger.info("webhook_payment_not_found", order_id=order_id)
            return {"status": "ok"}

        if payment.status == PaymentStatus.paid:
            return {"status": "ok"}

        payment.status = PaymentStatus.paid
        payment.razorpay_payment_id = payment_id

        if payment.scan_id:
            await db.execute(
                update(Scan).where(Scan.id == payment.scan_id).values(is_paid=True)
            )

        db.add(AuditLog(
            action="payment_completed_via_webhook",
            organization_id=payment.organization_id,
            resource_type="payment",
            resource_id=payment.id,
            metadata_json={"razorpay_order_id": order_id, "razorpay_payment_id": payment_id},
        ))
        await db.commit()
        logger.info("webhook_payment_captured", order_id=order_id)

    elif event == "payment.failed":
        try:
            order_id = payload["payload"]["payment"]["entity"]["order_id"]
        except (KeyError, TypeError):
            return {"status": "ok"}

        result = await db.execute(
            select(Payment).where(Payment.razorpay_order_id == order_id)
        )
        payment = result.scalar_one_or_none()
        if payment is not None and payment.status != PaymentStatus.paid:
            payment.status = PaymentStatus.failed
            await db.commit()
            logger.info("webhook_payment_failed", order_id=order_id)

    elif event == "subscription.charged":
        from datetime import timedelta
        from app.models.subscription import Subscription, SubscriptionStatus as SubStatus
        try:
            sub_id = payload["payload"]["subscription"]["entity"]["id"]
        except (KeyError, TypeError):
            return {"status": "ok"}

        sub_result = await db.execute(
            select(Subscription).where(Subscription.razorpay_subscription_id == sub_id)
        )
        sub = sub_result.scalar_one_or_none()
        if sub:
            today = datetime.now(tz=timezone.utc).date()
            sub.current_period_start = today
            sub.current_period_end = today + timedelta(days=30)
            sub.status = SubStatus.active

            org_sub_result = await db.execute(
                select(Organization).where(Organization.id == sub.organization_id)
            )
            org_sub = org_sub_result.scalar_one_or_none()
            if org_sub:
                from app.models.organization import SubscriptionStatus as OrgSubStatus
                org_sub.subscription_status = OrgSubStatus.active

            db.add(AuditLog(
                action="subscription_renewed",
                organization_id=sub.organization_id,
                metadata_json={"razorpay_subscription_id": sub_id},
            ))
            await db.commit()
            logger.info("webhook_subscription_charged", sub_id=sub_id)

    elif event == "subscription.cancelled":
        from app.models.subscription import Subscription, SubscriptionStatus as SubStatus
        try:
            sub_id = payload["payload"]["subscription"]["entity"]["id"]
        except (KeyError, TypeError):
            return {"status": "ok"}

        sub_result = await db.execute(
            select(Subscription).where(Subscription.razorpay_subscription_id == sub_id)
        )
        sub = sub_result.scalar_one_or_none()
        if sub:
            sub.status = SubStatus.cancelled
            sub.cancelled_at = datetime.now(tz=timezone.utc)

            org_sub_result = await db.execute(
                select(Organization).where(Organization.id == sub.organization_id)
            )
            org_sub = org_sub_result.scalar_one_or_none()
            if org_sub:
                from app.models.organization import SubscriptionStatus as OrgSubStatus
                org_sub.subscription_status = OrgSubStatus.cancelled

            db.add(AuditLog(
                action="subscription_cancelled_via_webhook",
                organization_id=sub.organization_id,
                metadata_json={"razorpay_subscription_id": sub_id},
            ))
            await db.commit()
            logger.info("webhook_subscription_cancelled", sub_id=sub_id)

    elif event == "subscription.halted":
        from app.models.subscription import Subscription, SubscriptionStatus as SubStatus
        try:
            sub_id = payload["payload"]["subscription"]["entity"]["id"]
        except (KeyError, TypeError):
            return {"status": "ok"}

        sub_result = await db.execute(
            select(Subscription).where(Subscription.razorpay_subscription_id == sub_id)
        )
        sub = sub_result.scalar_one_or_none()
        if sub:
            sub.status = SubStatus.past_due

            org_sub_result = await db.execute(
                select(Organization).where(Organization.id == sub.organization_id)
            )
            org_sub = org_sub_result.scalar_one_or_none()
            if org_sub:
                from app.models.organization import SubscriptionStatus as OrgSubStatus
                org_sub.subscription_status = OrgSubStatus.past_due

            db.add(AuditLog(
                action="subscription_payment_failed",
                organization_id=sub.organization_id,
                metadata_json={"razorpay_subscription_id": sub_id},
            ))
            await db.commit()
            logger.info("webhook_subscription_halted", sub_id=sub_id)

    else:
        logger.info("webhook_unhandled_event", webhook_event=event)

    return {"status": "ok"}
