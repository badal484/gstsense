import uuid
from datetime import date

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_admin
from app.core.logging import get_logger
from app.models.ca_firm import ReferralCommission, ReferralCommissionStatus
from app.models.organization import Organization
from app.models.payment import Payment, PaymentStatus
from app.models.scan import Scan
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.common import ApiResponse, make_response

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


class ProcessPayoutRequest(BaseModel):
    ca_firm_id: uuid.UUID
    commission_ids: list[uuid.UUID]
    payout_date: date


class PayoutResponse(BaseModel):
    processed: int
    message: str


class AdminStatsResponse(BaseModel):
    total_users: int
    total_organizations: int
    total_scans: int
    total_revenue_paise: int
    total_commissions_pending: int
    active_subscriptions: int


@router.post(
    "/payouts/process",
    response_model=ApiResponse[PayoutResponse],
    status_code=status.HTTP_200_OK,
    summary="Process commission payouts",
)
async def process_payouts(
    request_body: ProcessPayoutRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[PayoutResponse]:
    result = await db.execute(
        select(ReferralCommission).where(
            ReferralCommission.ca_firm_id == request_body.ca_firm_id,
            ReferralCommission.id.in_(request_body.commission_ids),
            ReferralCommission.status == ReferralCommissionStatus.pending,
        )
    )
    commissions = result.scalars().all()

    for commission in commissions:
        commission.status = ReferralCommissionStatus.paid
        commission.payout_date = request_body.payout_date  # type: ignore[assignment]

    await db.commit()

    count = len(commissions)
    logger.info("commissions_processed", count=count, ca_firm_id=str(request_body.ca_firm_id))
    return make_response(PayoutResponse(
        processed=count,
        message=f"Processed {count} commission(s) as paid.",
    ))


@router.get(
    "/stats",
    response_model=ApiResponse[AdminStatsResponse],
    status_code=status.HTTP_200_OK,
    summary="Platform-wide admin stats",
)
async def get_admin_stats(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[AdminStatsResponse]:
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    total_orgs = (await db.execute(select(func.count(Organization.id)))).scalar_one()
    total_scans = (await db.execute(select(func.count(Scan.id)))).scalar_one()

    revenue_result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(
            Payment.status == PaymentStatus.paid
        )
    )
    total_revenue_paise = int(revenue_result.scalar_one())

    pending_commissions = (await db.execute(
        select(func.count(ReferralCommission.id)).where(
            ReferralCommission.status == ReferralCommissionStatus.pending
        )
    )).scalar_one()

    active_subs = (await db.execute(
        select(func.count(Subscription.id)).where(
            Subscription.status == "active"
        )
    )).scalar_one()

    return make_response(AdminStatsResponse(
        total_users=total_users,
        total_organizations=total_orgs,
        total_scans=total_scans,
        total_revenue_paise=total_revenue_paise,
        total_commissions_pending=pending_commissions,
        active_subscriptions=active_subs,
    ))
