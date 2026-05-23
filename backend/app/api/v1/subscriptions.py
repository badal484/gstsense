from datetime import date, timedelta
from typing import Optional

import hashlib
import hmac

import razorpay
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org, get_current_user, get_db_session
from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.organization import Organization, Plan, SubscriptionStatus
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus as SubStatus
from app.models.user import User
from app.schemas.common import ApiResponse, make_response

logger = get_logger(__name__)
router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

PLAN_PRICES_PAISE: dict[str, int] = {
    "smb": 99900,
    "growth": 249900,
    "ca_firm": 999900,
}

PLAN_MAP: dict[str, Plan] = {
    "smb": Plan.smb,
    "growth": Plan.growth,
    "ca_firm": Plan.ca_firm,
}

SUB_PLAN_MAP: dict[str, SubscriptionPlan] = {
    "smb": SubscriptionPlan.smb,
    "growth": SubscriptionPlan.growth,
    "ca_firm": SubscriptionPlan.ca_firm,
}


def get_razorpay_client() -> razorpay.Client:
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


class CreateSubscriptionRequest(BaseModel):
    plan: str

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        if v not in PLAN_PRICES_PAISE:
            raise ValueError(f"Plan must be one of {list(PLAN_PRICES_PAISE.keys())}")
        return v


class SubscriptionResponse(BaseModel):
    id: str
    plan: str
    status: str
    razorpay_subscription_id: Optional[str]
    razorpay_key_id: Optional[str]
    current_period_start: str
    current_period_end: str
    amount_paise: int


@router.post(
    "/create",
    response_model=ApiResponse[SubscriptionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create subscription",
)
async def create_subscription(
    request_body: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[SubscriptionResponse]:
    # Check for any existing subscription (unique constraint: one row per org)
    existing_result = await db.execute(
        select(Subscription).where(Subscription.organization_id == org.id)
    )
    existing_sub = existing_result.scalar_one_or_none()

    # Block re-subscription only for active subscriptions.
    # Pending subscriptions (Razorpay created but not yet paid) can be re-attempted.
    if existing_sub is not None and existing_sub.status == SubStatus.active:
        raise ConflictError(
            message="Organisation already has an active subscription.",
            code="CF_004",
        )

    amount_paise = PLAN_PRICES_PAISE[request_body.plan]
    razorpay_sub_id: Optional[str] = None

    plan_id_map: dict[str, str] = {
        "smb": settings.RAZORPAY_PLAN_ID_SMB,
        "growth": settings.RAZORPAY_PLAN_ID_GROWTH,
        "ca_firm": settings.RAZORPAY_PLAN_ID_CA_FIRM,
    }
    razorpay_plan_id = plan_id_map[request_body.plan]

    if (
        not razorpay_plan_id
        or "placeholder" in razorpay_plan_id.lower()
        or not razorpay_plan_id.startswith("plan_")
    ):
        raise ValidationError(
            message=f"Razorpay Plan ID for '{request_body.plan}' is not configured. "
            "Please configure the plans in your Razorpay dashboard and update the environment variables.",
            code="PLAN_NOT_CONFIGURED",
        )

    try:
        client = get_razorpay_client()
        rz_sub = client.subscription.create(
            {
                "plan_id": razorpay_plan_id or f"plan_{request_body.plan}",
                "total_count": 120,
                "quantity": 1,
                "notes": {
                    "org_id": str(org.id),
                    "plan": request_body.plan,
                },
            }
        )
        razorpay_sub_id = rz_sub.get("id")
    except Exception as exc:
        logger.warning("razorpay_subscription_create_failed", error=str(exc))

    today = date.today()
    # If Razorpay returned a subscription ID, payment hasn't happened yet.
    # Keep the subscription as `pending` until /verify confirms the first payment.
    # If Razorpay is not configured (dev mode / no plan IDs set), activate immediately.
    activate_immediately = razorpay_sub_id is None
    sub_status = SubStatus.active if activate_immediately else SubStatus.pending

    if existing_sub is not None:
        existing_sub.plan = SUB_PLAN_MAP[request_body.plan]
        existing_sub.status = sub_status
        existing_sub.razorpay_subscription_id = razorpay_sub_id or existing_sub.razorpay_subscription_id
        existing_sub.current_period_start = today
        existing_sub.current_period_end = today + timedelta(days=30)
        existing_sub.cancelled_at = None
        existing_sub.cancellation_reason = None
        sub = existing_sub
    else:
        sub = Subscription(
            organization_id=org.id,
            plan=SUB_PLAN_MAP[request_body.plan],
            status=sub_status,
            razorpay_subscription_id=razorpay_sub_id,
            current_period_start=today,
            current_period_end=today + timedelta(days=30),
        )
        db.add(sub)

    # Only upgrade org plan immediately in dev mode (no Razorpay configured).
    # In production, org plan is upgraded by /verify after the user pays.
    if activate_immediately:
        org.plan = PLAN_MAP[request_body.plan]
        org.subscription_status = SubscriptionStatus.active
        org.billing_cycle_start = today
        org.billing_cycle_end = today + timedelta(days=30)

    db.add(AuditLog(
        action="subscription_created",
        user_id=current_user.id,
        organization_id=org.id,
        metadata_json={"plan": request_body.plan, "activate_immediately": activate_immediately},
    ))
    await db.commit()
    await db.refresh(sub)

    return make_response(
        SubscriptionResponse(
            id=str(sub.id),
            plan=sub.plan.value,
            status=sub.status.value,
            razorpay_subscription_id=sub.razorpay_subscription_id,
            razorpay_key_id=settings.RAZORPAY_KEY_ID if razorpay_sub_id else None,
            current_period_start=str(sub.current_period_start),
            current_period_end=str(sub.current_period_end),
            amount_paise=amount_paise,
        )
    )


@router.get(
    "/current",
    response_model=ApiResponse[Optional[SubscriptionResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get current subscription",
)
async def get_current_subscription(
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[Optional[SubscriptionResponse]]:
    result = await db.execute(
        select(Subscription)
        .where(Subscription.organization_id == org.id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub = result.scalar_one_or_none()
    if sub is None or sub.status != SubStatus.active:
        raise NotFoundError(
            message="No active subscription found for this organization.",
            code="NF_SUB_001",
        )

    return make_response(
        SubscriptionResponse(
            id=str(sub.id),
            plan=sub.plan.value,
            status=sub.status.value,
            razorpay_subscription_id=sub.razorpay_subscription_id,
            razorpay_key_id=None,
            current_period_start=str(sub.current_period_start),
            current_period_end=str(sub.current_period_end),
            amount_paise=PLAN_PRICES_PAISE.get(sub.plan.value, 0),
        )
    )


@router.post(
    "/cancel",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Cancel subscription",
)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    result = await db.execute(
        select(Subscription).where(
            Subscription.organization_id == org.id,
            Subscription.status == SubStatus.active,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise NotFoundError(
            message="No active subscription found.",
            code="NF_010",
        )

    if sub.razorpay_subscription_id:
        try:
            client = get_razorpay_client()
            client.subscription.cancel(sub.razorpay_subscription_id, {"cancel_at_cycle_end": 1})
        except Exception as exc:
            logger.warning("razorpay_cancel_failed", error=str(exc))

    sub.status = SubStatus.cancelled
    org.subscription_status = SubscriptionStatus.cancelled

    db.add(AuditLog(
        action="subscription_cancelled",
        user_id=current_user.id,
        organization_id=org.id,
        metadata_json={"plan": sub.plan.value},
    ))
    await db.commit()

    return make_response({
        "message": "Subscription cancelled. Access continues until end of current period.",
        "access_until": str(sub.current_period_end),
    })


# ---------------------------------------------------------------------------
# Verify subscription payment
# ---------------------------------------------------------------------------

class VerifySubscriptionRequest(BaseModel):
    razorpay_subscription_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post(
    "/verify",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Verify Razorpay subscription payment",
)
async def verify_subscription(
    body: VerifySubscriptionRequest,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    # 1. Verify HMAC-SHA256 signature
    message = f"{body.razorpay_payment_id}|{body.razorpay_subscription_id}".encode()
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise ValidationError(
            message="Subscription payment verification failed.",
            code="VAL_001",
        )

    # 2. Find subscription
    result = await db.execute(
        select(Subscription).where(
            Subscription.razorpay_subscription_id == body.razorpay_subscription_id,
            Subscription.organization_id == org.id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise NotFoundError(message="Subscription not found.", code="NF_010")

    # 3. Activate — upgrade org plan and mark subscription active
    today = date.today()
    sub.status = SubStatus.active
    org.plan = PLAN_MAP.get(sub.plan.value, Plan.smb)
    org.subscription_status = SubscriptionStatus.active
    org.billing_cycle_start = today
    org.billing_cycle_end = today + timedelta(days=30)

    db.add(AuditLog(
        action="subscription_verified",
        user_id=current_user.id,
        organization_id=org.id,
        metadata_json={
            "razorpay_subscription_id": body.razorpay_subscription_id,
            "razorpay_payment_id": body.razorpay_payment_id,
            "plan": sub.plan.value,
        },
    ))
    await db.commit()
    logger.info("subscription_verified", org_id=str(org.id), plan=sub.plan.value)

    return make_response({
        "success": True,
        "plan": sub.plan.value,
        "message": "Subscription activated successfully.",
    })
