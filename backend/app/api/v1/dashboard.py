"""Single-call dashboard endpoint — all data in one response."""

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org, get_current_user, get_db_session
from app.core.logging import get_logger
from app.models.compliance_score import ComplianceScoreRecord
from app.models.notice import DraftStatus, Notice
from app.models.organization import Organization
from app.models.scan import Scan, ScanStatus
from app.schemas.common import ApiResponse, make_response
from app.services.compliance_score import calculate_org_compliance_score
from fastapi import Query as FQuery
from app.models.user import User

logger = get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class RecentScanSummary(BaseModel):
    id: str
    scan_month: str
    total_mismatches: int
    total_rupee_risk: Decimal
    status: str
    is_paid: bool
    created_at: str


class DashboardResponse(BaseModel):
    compliance_score: int
    compliance_grade: str
    compliance_color: str
    compliance_factors: list[dict]
    recommendations: list[str]

    total_scans: int
    total_mismatches_found: int
    total_rupee_risk_found: Decimal
    total_itc_recovered: Decimal
    scans_this_month: int

    invoice_limit: int
    invoices_used_this_month: int
    invoice_usage_percentage: float

    next_gstr1_deadline: str
    next_gstr3b_deadline: str
    days_to_gstr1: int
    days_to_gstr3b: int

    recent_scans: list[RecentScanSummary]
    pending_notices: int
    score_trend: str


def _next_deadline(day_of_month: int, today: date) -> date:
    """Return the next occurrence of day_of_month on or after today."""
    if today.day <= day_of_month:
        try:
            return today.replace(day=day_of_month)
        except ValueError:
            pass
    # Move to next month
    if today.month == 12:
        return date(today.year + 1, 1, day_of_month)
    # Some months have fewer days — clamp
    last_day = calendar.monthrange(today.year, today.month + 1)[1]
    target_day = min(day_of_month, last_day)
    return date(today.year, today.month + 1, target_day)


@router.get(
    "/",
    response_model=ApiResponse[DashboardResponse],
    summary="Get complete dashboard data in one call",
)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[DashboardResponse]:
    org_id = str(org.id)

    # 1. Compliance score — use today's stored record if available (avoids re-calculation on every page load)
    today = date.today()
    stored_q = await db.execute(
        select(ComplianceScoreRecord)
        .where(
            ComplianceScoreRecord.organization_id == org.id,
            func.date(ComplianceScoreRecord.calculated_at) == today,
        )
        .order_by(desc(ComplianceScoreRecord.calculated_at))
        .limit(1)
    )
    stored_score = stored_q.scalar_one_or_none()

    # Always calculate for fresh factors/recommendations; use stored record only for history
    compliance = await calculate_org_compliance_score(org_id, db)
    if stored_score is None:
        new_record = ComplianceScoreRecord(
            organization_id=org.id,
            score=compliance.score,
            grade=compliance.grade,
        )
        db.add(new_record)
        await db.commit()

    # 2. All-time usage stats
    all_scans_q = await db.execute(
        select(Scan).where(
            Scan.organization_id == org.id,
            Scan.status == ScanStatus.completed,
        )
    )
    all_completed = all_scans_q.scalars().all()
    total_scans = len(all_completed)
    total_mismatches_found = sum(s.total_mismatches for s in all_completed)
    total_rupee_risk_found = sum((s.total_rupee_risk for s in all_completed), Decimal("0"))

    # ITC recovered from latest completed ITC scan
    from app.models.itc_scan import ITCScan, ITCScanStatus
    itc_q = await db.execute(
        select(ITCScan).where(
            ITCScan.organization_id == org.id,
            ITCScan.status == ITCScanStatus.completed,
        ).order_by(ITCScan.created_at.desc()).limit(1)
    )
    latest_itc = itc_q.scalar_one_or_none()
    total_itc_recovered = (
        latest_itc.total_unclaimed_itc if latest_itc else Decimal("0")
    )

    # Scans this month
    month_start = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
    scans_this_month = sum(
        1 for s in all_completed if s.created_at >= month_start
    )

    # 3. Invoice usage
    invoice_limit = org.invoice_limit
    invoices_used = org.invoices_used_this_month
    invoice_usage_pct = (invoices_used / invoice_limit * 100) if invoice_limit > 0 else 0.0

    # 4. GST deadlines
    gstr1_deadline = _next_deadline(11, today)
    gstr3b_deadline = _next_deadline(20, today)
    days_to_gstr1 = (gstr1_deadline - today).days
    days_to_gstr3b = (gstr3b_deadline - today).days

    def fmt_date(d: date) -> str:
        return d.strftime("%-d %B %Y")

    # 5. Recent 5 scans (all statuses)
    recent_q = await db.execute(
        select(Scan).where(Scan.organization_id == org.id)
        .order_by(Scan.created_at.desc())
        .limit(5)
    )
    recent_raw = recent_q.scalars().all()
    recent_scans = [
        RecentScanSummary(
            id=str(s.id),
            scan_month=s.scan_month,
            total_mismatches=s.total_mismatches,
            total_rupee_risk=s.total_rupee_risk,
            status=s.status.value,
            is_paid=s.is_paid,
            created_at=s.created_at.isoformat(),
        )
        for s in recent_raw
    ]

    # 6. Pending notices
    notices_q = await db.execute(
        select(func.count()).where(
            Notice.organization_id == org.id,
            Notice.draft_status.in_([DraftStatus.pending, DraftStatus.generated, DraftStatus.reviewed]),
        )
    )
    pending_notices = notices_q.scalar() or 0

    # 7. Compute trend by comparing today's score to 30 days ago
    from datetime import timedelta as _td
    cutoff_30 = datetime.now(tz=timezone.utc) - _td(days=30)
    old_q = await db.execute(
        select(ComplianceScoreRecord)
        .where(
            ComplianceScoreRecord.organization_id == org.id,
            ComplianceScoreRecord.calculated_at <= cutoff_30,
        )
        .order_by(desc(ComplianceScoreRecord.calculated_at))
        .limit(1)
    )
    old_record = old_q.scalar_one_or_none()
    if old_record is not None:
        delta = compliance.score - old_record.score
        score_trend = "improving" if delta >= 5 else ("declining" if delta <= -5 else "stable")
    else:
        score_trend = "stable"

    return make_response(DashboardResponse(
        compliance_score=compliance.score,
        compliance_grade=compliance.grade,
        compliance_color=compliance.color,
        compliance_factors=compliance.factors,
        recommendations=compliance.recommendations,
        total_scans=total_scans,
        total_mismatches_found=total_mismatches_found,
        total_rupee_risk_found=total_rupee_risk_found,
        total_itc_recovered=total_itc_recovered,
        scans_this_month=scans_this_month,
        invoice_limit=invoice_limit,
        invoices_used_this_month=invoices_used,
        invoice_usage_percentage=round(invoice_usage_pct, 1),
        next_gstr1_deadline=fmt_date(gstr1_deadline),
        next_gstr3b_deadline=fmt_date(gstr3b_deadline),
        days_to_gstr1=days_to_gstr1,
        days_to_gstr3b=days_to_gstr3b,
        recent_scans=recent_scans,
        pending_notices=pending_notices,
        score_trend=score_trend,
    ))


@router.get(
    "/score-history",
    response_model=ApiResponse[list],
    summary="Get compliance score history",
)
async def get_score_history(
    days: int = FQuery(default=30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list]:
    from datetime import timedelta as _td2
    cutoff = datetime.now(tz=timezone.utc) - _td2(days=days)
    result = await db.execute(
        select(ComplianceScoreRecord)
        .where(
            ComplianceScoreRecord.organization_id == org.id,
            ComplianceScoreRecord.calculated_at >= cutoff,
        )
        .order_by(ComplianceScoreRecord.calculated_at.asc())
    )
    records = result.scalars().all()
    history = [
        {
            "date": r.calculated_at.strftime("%Y-%m-%d"),
            "score": r.score,
            "grade": r.grade,
        }
        for r in records
    ]
    return make_response(history)
