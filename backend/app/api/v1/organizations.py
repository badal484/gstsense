from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org, get_current_user, get_db_session
from app.models.mismatch import Mismatch
from app.models.organization import Organization
from app.models.scan import Scan, ScanStatus
from app.models.user import User
from app.schemas.common import ApiResponse, make_response
from app.schemas.organization import OrganizationDetailResponse, UsageStatsResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get(
    "/me",
    response_model=ApiResponse[OrganizationDetailResponse],
    summary="Get current organization",
)
async def get_my_organization(
    org: Organization = Depends(get_current_org),
) -> ApiResponse[OrganizationDetailResponse]:
    """Return the current user's organization details."""
    return make_response(OrganizationDetailResponse.model_validate(org))


@router.get(
    "/me/stats",
    response_model=ApiResponse[UsageStatsResponse],
    summary="Get organization usage statistics",
)
async def get_usage_stats(
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[UsageStatsResponse]:
    """Return aggregate usage statistics for the organization."""
    # 1. Total scans (all time)
    total_scans_result = await db.execute(
        select(func.count(Scan.id)).where(Scan.organization_id == org.id)
    )
    total_scans = total_scans_result.scalar_one() or 0

    # 2. Total mismatches found across all completed scans
    total_mismatches_result = await db.execute(
        select(func.coalesce(func.sum(Scan.total_mismatches), 0))
        .where(Scan.organization_id == org.id, Scan.status == ScanStatus.completed)
    )
    total_mismatches_found = int(total_mismatches_result.scalar_one() or 0)

    # 3. Total rupee risk found
    total_risk_result = await db.execute(
        select(func.coalesce(func.sum(Scan.total_rupee_risk), 0))
        .where(Scan.organization_id == org.id, Scan.status == ScanStatus.completed)
    )
    total_rupee_risk_found = Decimal(str(total_risk_result.scalar_one() or 0))

    # 4. Scans this calendar month
    now = datetime.now(tz=timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    scans_month_result = await db.execute(
        select(func.count(Scan.id)).where(
            Scan.organization_id == org.id,
            Scan.created_at >= month_start,
        )
    )
    scans_this_month = scans_month_result.scalar_one() or 0

    return make_response(UsageStatsResponse(
        total_scans=total_scans,
        total_mismatches_found=total_mismatches_found,
        total_rupee_risk_found=total_rupee_risk_found,
        total_itc_recovered=Decimal("0"),
        scans_this_month=scans_this_month,
        invoices_used_this_month=org.invoices_used_this_month,
        invoice_limit=org.invoice_limit,
    ))
