"""Compliance health score calculator for GST organisations."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ComplianceScore:
    score: int
    grade: str
    color: str
    factors: list[dict]
    recommendations: list[str]
    trend: str


def get_compliance_grade(score: int) -> tuple[str, str]:
    """Return (grade, color) for a given score."""
    if score >= 90:
        return "A+", "#1D9E75"
    if score >= 75:
        return "A", "#1D9E75"
    if score >= 60:
        return "B", "#BA7517"
    if score >= 45:
        return "C", "#E24B4A"
    return "D", "#E24B4A"


def calculate_compliance_score(
    total_mismatches_last_3_months: int,
    total_rupee_risk_last_3_months: Decimal,
    scans_run_last_3_months: int,
    has_pending_notices: bool,
    itc_leakage_amount: Decimal,
    days_since_last_scan: Optional[int],
    subscription_active: bool,
) -> ComplianceScore:
    """Calculate compliance health score 0–100."""
    score = 100
    factors: list[dict] = []
    recommendations: list[str] = []

    # ------------------------------------------------------------------ #
    # 1. Mismatch penalty
    # ------------------------------------------------------------------ #
    m = total_mismatches_last_3_months
    if m == 0:
        mismatch_deduction = 0
        factors.append({
            "name": "Mismatch Detection",
            "status": "good",
            "description": "No mismatches found in the last 3 months",
            "points": "0",
        })
    elif m <= 5:
        mismatch_deduction = 10
        factors.append({
            "name": "Mismatch Detection",
            "status": "warning",
            "description": f"{m} mismatch(es) found in the last 3 months",
            "points": "-10",
        })
    elif m <= 10:
        mismatch_deduction = 20
        factors.append({
            "name": "Mismatch Detection",
            "status": "warning",
            "description": f"{m} mismatches found — review urgently",
            "points": "-20",
        })
    elif m <= 20:
        mismatch_deduction = 35
        factors.append({
            "name": "Mismatch Detection",
            "status": "critical",
            "description": f"{m} mismatches detected — high non-compliance risk",
            "points": "-35",
        })
    else:
        mismatch_deduction = 50
        factors.append({
            "name": "Mismatch Detection",
            "status": "critical",
            "description": f"{m} mismatches detected — critical compliance failure",
            "points": "-50",
        })
        recommendations.append(
            "Run a scan immediately and fix all mismatches before your next filing deadline."
        )
    score -= mismatch_deduction

    # ------------------------------------------------------------------ #
    # 2. Rupee risk penalty
    # ------------------------------------------------------------------ #
    risk = total_rupee_risk_last_3_months
    if risk <= Decimal("0"):
        risk_deduction = 0
        factors.append({
            "name": "Financial Risk Exposure",
            "status": "good",
            "description": "No financial risk detected",
            "points": "0",
        })
    elif risk <= Decimal("10000"):
        risk_deduction = 5
        factors.append({
            "name": "Financial Risk Exposure",
            "status": "good",
            "description": f"Low risk exposure: ₹{risk:,.2f}",
            "points": "-5",
        })
    elif risk <= Decimal("100000"):
        risk_deduction = 15
        factors.append({
            "name": "Financial Risk Exposure",
            "status": "warning",
            "description": f"Moderate risk exposure: ₹{risk:,.2f}",
            "points": "-15",
        })
    elif risk <= Decimal("500000"):
        risk_deduction = 25
        factors.append({
            "name": "Financial Risk Exposure",
            "status": "warning",
            "description": f"High risk exposure: ₹{risk:,.2f}",
            "points": "-25",
        })
    else:
        risk_deduction = 35
        factors.append({
            "name": "Financial Risk Exposure",
            "status": "critical",
            "description": f"Critical risk exposure: ₹{risk:,.2f}",
            "points": "-35",
        })
    score -= risk_deduction

    # ------------------------------------------------------------------ #
    # 3. Pending notice penalty
    # ------------------------------------------------------------------ #
    if has_pending_notices:
        score -= 20
        factors.append({
            "name": "GST Notices",
            "status": "critical",
            "description": "Pending GST notice(s) require immediate action",
            "points": "-20",
        })
        recommendations.append(
            "You have pending GST notices. Upload them to GSTSense to get AI-drafted replies."
        )
    else:
        factors.append({
            "name": "GST Notices",
            "status": "good",
            "description": "No pending notices",
            "points": "0",
        })

    # ------------------------------------------------------------------ #
    # 4. ITC leakage penalty
    # ------------------------------------------------------------------ #
    itc = itc_leakage_amount
    if itc <= Decimal("0"):
        itc_deduction = 0
        factors.append({
            "name": "ITC Recovery",
            "status": "good",
            "description": "No unclaimed ITC detected",
            "points": "0",
        })
    elif itc <= Decimal("10000"):
        itc_deduction = 5
        factors.append({
            "name": "ITC Recovery",
            "status": "warning",
            "description": f"₹{itc:,.2f} in unclaimed ITC",
            "points": "-5",
        })
    elif itc <= Decimal("50000"):
        itc_deduction = 10
        factors.append({
            "name": "ITC Recovery",
            "status": "warning",
            "description": f"₹{itc:,.2f} in unclaimed ITC",
            "points": "-10",
        })
        recommendations.append(
            f"You have ₹{itc:,.2f} in unclaimed ITC. Run an ITC analysis to recover this money."
        )
    else:
        itc_deduction = 15
        factors.append({
            "name": "ITC Recovery",
            "status": "critical",
            "description": f"₹{itc:,.2f} in unclaimed ITC",
            "points": "-15",
        })
        recommendations.append(
            f"You have ₹{itc:,.2f} in unclaimed ITC. Run an ITC analysis to recover this money."
        )
    score -= itc_deduction

    # ------------------------------------------------------------------ #
    # 5. Scan frequency
    # ------------------------------------------------------------------ #
    if days_since_last_scan is None:
        score -= 20
        factors.append({
            "name": "Scan Frequency",
            "status": "critical",
            "description": "No scans have been run yet",
            "points": "-20",
        })
        recommendations.append(
            "You haven't run any scans. Upload your GSTR files to check for mismatches."
        )
    elif days_since_last_scan <= 31:
        score += 5
        factors.append({
            "name": "Scan Frequency",
            "status": "good",
            "description": f"Scanned recently ({days_since_last_scan} days ago)",
            "points": "+5",
        })
    elif days_since_last_scan <= 60:
        score -= 5
        factors.append({
            "name": "Scan Frequency",
            "status": "warning",
            "description": f"Last scanned {days_since_last_scan} days ago",
            "points": "-5",
        })
        recommendations.append(
            f"You haven't scanned in {days_since_last_scan} days. Run a scan before your next filing deadline."
        )
    else:
        score -= 15
        factors.append({
            "name": "Scan Frequency",
            "status": "critical",
            "description": f"Last scanned {days_since_last_scan} days ago — overdue",
            "points": "-15",
        })
        recommendations.append(
            f"You haven't scanned in {days_since_last_scan} days. Run a scan before your next filing deadline."
        )

    # ------------------------------------------------------------------ #
    # 6. Subscription bonus
    # ------------------------------------------------------------------ #
    if subscription_active:
        score += 5
        factors.append({
            "name": "Active Subscription",
            "status": "good",
            "description": "Active subscription — full feature access",
            "points": "+5",
        })
    else:
        factors.append({
            "name": "Active Subscription",
            "status": "warning",
            "description": "No active subscription",
            "points": "0",
        })

    # ------------------------------------------------------------------ #
    # Clamp and finalize
    # ------------------------------------------------------------------ #
    score = max(0, min(100, score))
    grade, color = get_compliance_grade(score)

    if score >= 90 and not recommendations:
        recommendations.append(
            "Excellent compliance! Keep running monthly scans to maintain your clean record."
        )

    logger.info(
        "compliance_score_calculated",
        score=score,
        grade=grade,
        mismatches=total_mismatches_last_3_months,
        has_notices=has_pending_notices,
    )

    return ComplianceScore(
        score=score,
        grade=grade,
        color=color,
        factors=factors,
        recommendations=recommendations,
        trend="stable",
    )


async def calculate_org_compliance_score(
    org_id: str,
    db: AsyncSession,
) -> ComplianceScore:
    """Fetch all required data and calculate compliance score for an organisation."""
    from app.models.itc_scan import ITCScan, ITCScanStatus
    from app.models.mismatch import Mismatch
    from app.models.notice import DraftStatus, Notice
    from app.models.organization import Organization, SubscriptionStatus
    from app.models.scan import Scan, ScanStatus

    org_uuid = uuid.UUID(org_id) if isinstance(org_id, str) else org_id
    three_months_ago = datetime.now(tz=timezone.utc) - timedelta(days=90)

    # 1-3. Scans + mismatches + risk from last 3 months
    scans_q = await db.execute(
        select(Scan).where(
            Scan.organization_id == org_uuid,
            Scan.status == ScanStatus.completed,
            Scan.created_at >= three_months_ago,
        )
    )
    recent_scans = scans_q.scalars().all()
    scans_run = len(recent_scans)
    total_mismatches = sum(s.total_mismatches for s in recent_scans)
    total_risk = sum((s.total_rupee_risk for s in recent_scans), Decimal("0"))

    # 4. Pending notices
    notices_q = await db.execute(
        select(func.count()).where(
            Notice.organization_id == org_uuid,
            Notice.draft_status.in_([DraftStatus.pending, DraftStatus.generated]),
        )
    )
    pending_notices_count = notices_q.scalar() or 0

    # 5. Latest ITC unclaimed
    itc_q = await db.execute(
        select(ITCScan).where(
            ITCScan.organization_id == org_uuid,
            ITCScan.status == ITCScanStatus.completed,
        ).order_by(ITCScan.created_at.desc()).limit(1)
    )
    latest_itc = itc_q.scalar_one_or_none()
    itc_leakage = latest_itc.total_unclaimed_itc if latest_itc else Decimal("0")

    # 6. Days since last scan
    days_since_last: Optional[int] = None
    all_scans_q = await db.execute(
        select(Scan).where(
            Scan.organization_id == org_uuid,
            Scan.status == ScanStatus.completed,
        ).order_by(Scan.completed_at.desc()).limit(1)
    )
    last_scan = all_scans_q.scalar_one_or_none()
    if last_scan and last_scan.completed_at:
        completed = last_scan.completed_at
        if completed.tzinfo is None:
            completed = completed.replace(tzinfo=timezone.utc)
        delta = datetime.now(tz=timezone.utc) - completed
        days_since_last = delta.days

    # 7. Subscription active
    org_q = await db.execute(select(Organization).where(Organization.id == org_uuid))
    org = org_q.scalar_one_or_none()
    subscription_active = (
        org is not None and
        org.subscription_status in (SubscriptionStatus.active, SubscriptionStatus.trialing)
    )

    return calculate_compliance_score(
        total_mismatches_last_3_months=total_mismatches,
        total_rupee_risk_last_3_months=total_risk,
        scans_run_last_3_months=scans_run,
        has_pending_notices=pending_notices_count > 0,
        itc_leakage_amount=itc_leakage,
        days_since_last_scan=days_since_last,
        subscription_active=subscription_active,
    )
