from datetime import date, timedelta
from typing import Optional

import razorpay
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org, get_current_user, get_db_session
from app.core.config import settings
from app.core.exceptions import ConflictError, ExternalServiceError, NotFoundError
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
    existing = await db.execute(
        select(Subscription).where(
            Subscription.organization_id == org.id,
            Subscription.status == SubStatus.active,
        )
    )
    if existing.scalar_one_or_none() is not None:
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
    sub = Subscription(
        organization_id=org.id,
        plan=SUB_PLAN_MAP[request_body.plan],
        status=SubStatus.active,
        razorpay_subscription_id=razorpay_sub_id,
        current_period_start=today,
        current_period_end=today + timedelta(days=30),
    )
    db.add(sub)

    org.plan = PLAN_MAP[request_body.plan]
    org.subscription_status = SubscriptionStatus.active
    org.billing_cycle_start = today
    org.billing_cycle_end = today + timedelta(days=30)

    db.add(AuditLog(
        action="subscription_created",
        user_id=current_user.id,
        organization_id=org.id,
        metadata_json={"plan": request_body.plan},
    ))
    await db.commit()
    await db.refresh(sub)

    return make_response(
        SubscriptionResponse(
            id=str(sub.id),
            plan=sub.plan.value,
            status=sub.status.value,
            razorpay_subscription_id=sub.razorpay_subscription_id,
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
        select(Subscription).where(Subscription.organization_id == org.id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        return make_response(None)

    return make_response(
        SubscriptionResponse(
            id=str(sub.id),
            plan=sub.plan.value,
            status=sub.status.value,
            razorpay_subscription_id=sub.razorpay_subscription_id,
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
            client.subscription.cancel(sub.razorpay_subscription_id)
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
