"""CA Firm White-Label System API endpoints."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org, get_current_user, get_db_session, require_plan
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.ca_firm import (
    CAClientRelationship,
    CAClientStatus,
    CAFirm,
    ReferralCommission,
    ReferralCommissionStatus,
)
from app.models.organization import Organization
from app.models.user import User
from app.schemas.ca_firm import (
    AddClientRequest,
    BrandingResponse,
    CAClientResponse,
    CADashboardStats,
    CAFirmCreate,
    CAFirmResponse,
    CAFirmUpdate,
    CommissionSummary,
    ReferralCommissionResponse,
)
from app.schemas.common import ApiResponse, make_response
from app.services.referral_service import get_ca_firm_for_user

logger = get_logger(__name__)

router = APIRouter(prefix="/ca-firms", tags=["CA Firms"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_ca_firm_or_404(db: AsyncSession, user_id: uuid.UUID) -> CAFirm:
    ca_firm = await get_ca_firm_for_user(db, user_id)
    if ca_firm is None:
        raise NotFoundError(
            message="CA firm profile not found. Please register your firm first.",
            code="NF_CA_001",
        )
    return ca_firm


def _build_client_response(rel: CAClientRelationship) -> CAClientResponse:
    org = rel.organization
    return CAClientResponse(
        id=rel.id,
        ca_firm_id=rel.ca_firm_id,
        organization_id=rel.organization_id,
        organization_name=org.business_name,
        organization_gstin=org.gstin,
        status=rel.status.value,
        referral_commission_rate=rel.referral_commission_rate,
        created_at=rel.created_at,
    )


def _build_commission_response(c: ReferralCommission) -> ReferralCommissionResponse:
    org = c.organization
    return ReferralCommissionResponse(
        id=c.id,
        ca_firm_id=c.ca_firm_id,
        organization_id=c.organization_id,
        organization_name=org.business_name,
        payment_id=c.payment_id,
        commission_amount=c.commission_amount,
        commission_rate=c.commission_rate,
        status=c.status.value,
        payout_date=c.payout_date,
        created_at=c.created_at,
    )


# ---------------------------------------------------------------------------
# Registration & Profile
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=ApiResponse[CAFirmResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register CA firm profile",
)
async def register_ca_firm(
    body: CAFirmCreate,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[CAFirmResponse]:
    # One firm per user
    existing = await get_ca_firm_for_user(db, current_user.id)
    if existing is not None:
        raise ConflictError(
            message="You already have a CA firm profile registered.",
            code="CF_001",
        )

    # Subdomain uniqueness check
    if body.white_label_subdomain:
        dup = await db.execute(
            select(CAFirm).where(CAFirm.white_label_subdomain == body.white_label_subdomain)
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictError(
                message=f"Subdomain '{body.white_label_subdomain}' is already taken.",
                code="CF_002",
            )

    ca_firm = CAFirm(
        owner_user_id=current_user.id,
        firm_name=body.firm_name,
        icai_firm_registration_number=body.icai_firm_registration_number,
        primary_ca_name=body.primary_ca_name,
        icai_membership_number=body.icai_membership_number,
        phone=body.phone,
        city=body.city,
        state=body.state,
        white_label_subdomain=body.white_label_subdomain,
        primary_color=body.primary_color,
    )
    db.add(ca_firm)

    db.add(AuditLog(
        action="ca_firm_registered",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="ca_firm",
        resource_id=ca_firm.id,
        metadata_json={"firm_name": body.firm_name},
    ))

    await db.commit()
    await db.refresh(ca_firm)
    logger.info("ca_firm_registered", firm_id=str(ca_firm.id))

    return make_response(CAFirmResponse.model_validate(ca_firm))


@router.get(
    "/me",
    response_model=ApiResponse[CAFirmResponse],
    summary="Get current CA firm profile",
)
async def get_ca_firm(
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[CAFirmResponse]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)
    return make_response(CAFirmResponse.model_validate(ca_firm))


@router.patch(
    "/me",
    response_model=ApiResponse[CAFirmResponse],
    summary="Update CA firm profile",
)
async def update_ca_firm(
    body: CAFirmUpdate,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[CAFirmResponse]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    if body.white_label_subdomain and body.white_label_subdomain != ca_firm.white_label_subdomain:
        dup = await db.execute(
            select(CAFirm).where(CAFirm.white_label_subdomain == body.white_label_subdomain)
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictError(
                message=f"Subdomain '{body.white_label_subdomain}' is already taken.",
                code="CF_002",
            )

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(ca_firm, field, value)

    await db.commit()
    await db.refresh(ca_firm)
    return make_response(CAFirmResponse.model_validate(ca_firm))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/me/dashboard",
    response_model=ApiResponse[CADashboardStats],
    summary="CA firm dashboard statistics",
)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[CADashboardStats]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)
    firm_id = ca_firm.id

    # Active client count
    active_q = await db.execute(
        select(func.count()).where(
            CAClientRelationship.ca_firm_id == firm_id,
            CAClientRelationship.status == CAClientStatus.active,
        )
    )
    active_clients = active_q.scalar() or 0

    # Commission aggregates
    pending_q = await db.execute(
        select(func.coalesce(func.sum(ReferralCommission.commission_amount), 0)).where(
            ReferralCommission.ca_firm_id == firm_id,
            ReferralCommission.status == ReferralCommissionStatus.pending,
        )
    )
    total_pending = Decimal(str(pending_q.scalar() or 0))

    paid_q = await db.execute(
        select(func.coalesce(func.sum(ReferralCommission.commission_amount), 0)).where(
            ReferralCommission.ca_firm_id == firm_id,
            ReferralCommission.status == ReferralCommissionStatus.paid,
        )
    )
    total_paid = Decimal(str(paid_q.scalar() or 0))

    # This month's commissions
    now = datetime.now(tz=timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_q = await db.execute(
        select(func.coalesce(func.sum(ReferralCommission.commission_amount), 0)).where(
            ReferralCommission.ca_firm_id == firm_id,
            ReferralCommission.created_at >= month_start,
        )
    )
    commissions_this_month = Decimal(str(month_q.scalar() or 0))

    # Recent clients (last 5)
    recent_rel_q = await db.execute(
        select(CAClientRelationship)
        .where(CAClientRelationship.ca_firm_id == firm_id)
        .order_by(CAClientRelationship.created_at.desc())
        .limit(5)
    )
    recent_clients = [_build_client_response(r) for r in recent_rel_q.scalars().all()]

    # Recent commissions (last 5)
    recent_com_q = await db.execute(
        select(ReferralCommission)
        .where(ReferralCommission.ca_firm_id == firm_id)
        .order_by(ReferralCommission.created_at.desc())
        .limit(5)
    )
    recent_commissions = [_build_commission_response(c) for c in recent_com_q.scalars().all()]

    return make_response(CADashboardStats(
        total_clients=ca_firm.total_clients,
        active_clients=active_clients,
        total_commissions_pending=total_pending,
        total_commissions_paid=total_paid,
        total_commissions_all_time=Decimal(str(ca_firm.total_referral_earnings)),
        commissions_this_month=commissions_this_month,
        recent_clients=recent_clients,
        recent_commissions=recent_commissions,
    ))


# ---------------------------------------------------------------------------
# Client Management
# ---------------------------------------------------------------------------


@router.post(
    "/clients",
    response_model=ApiResponse[CAClientResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add client organization by GSTIN",
)
async def add_client(
    body: AddClientRequest,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[CAClientResponse]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    # Find the organization by GSTIN
    org_q = await db.execute(
        select(Organization).where(Organization.gstin == body.gstin)
    )
    client_org = org_q.scalar_one_or_none()
    if client_org is None:
        raise NotFoundError(
            message=f"No organization found with GSTIN '{body.gstin}'.",
            code="NF_CA_002",
        )

    # Cannot add own org
    if client_org.id == org.id:
        raise ValidationError(
            message="You cannot add your own organization as a client.",
            code="VAL_CA_001",
        )

    # Check for existing relationship
    existing_q = await db.execute(
        select(CAClientRelationship).where(
            CAClientRelationship.ca_firm_id == ca_firm.id,
            CAClientRelationship.organization_id == client_org.id,
        )
    )
    existing_rel = existing_q.scalar_one_or_none()

    if existing_rel is not None:
        if existing_rel.status == CAClientStatus.active:
            raise ConflictError(
                message="This organization is already a client of your firm.",
                code="CF_003",
            )
        # Re-activate removed relationship
        existing_rel.status = CAClientStatus.active
        existing_rel.referral_commission_rate = body.commission_rate
        await db.commit()
        await db.refresh(existing_rel)
        return make_response(_build_client_response(existing_rel))

    rel = CAClientRelationship(
        ca_firm_id=ca_firm.id,
        organization_id=client_org.id,
        referral_commission_rate=body.commission_rate,
    )
    db.add(rel)

    ca_firm.total_clients = ca_firm.total_clients + 1

    db.add(AuditLog(
        action="ca_client_added",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="ca_client_relationship",
        resource_id=rel.id,
        metadata_json={"client_gstin": body.gstin, "commission_rate": str(body.commission_rate)},
    ))

    await db.commit()
    await db.refresh(rel)
    logger.info("ca_client_added", firm_id=str(ca_firm.id), org_id=str(client_org.id))

    return make_response(_build_client_response(rel))


@router.get(
    "/clients",
    response_model=ApiResponse[list[CAClientResponse]],
    summary="List all clients",
)
async def list_clients(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[CAClientResponse]]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    q = select(CAClientRelationship).where(
        CAClientRelationship.ca_firm_id == ca_firm.id
    )
    if status_filter in ("active", "removed"):
        q = q.where(CAClientRelationship.status == CAClientStatus(status_filter))
    else:
        q = q.where(CAClientRelationship.status == CAClientStatus.active)

    result = await db.execute(q.order_by(CAClientRelationship.created_at.desc()))
    clients = [_build_client_response(r) for r in result.scalars().all()]
    return make_response(clients)


@router.get(
    "/clients/{org_id}",
    response_model=ApiResponse[CAClientResponse],
    summary="Get client details",
)
async def get_client(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[CAClientResponse]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    rel_q = await db.execute(
        select(CAClientRelationship).where(
            CAClientRelationship.ca_firm_id == ca_firm.id,
            CAClientRelationship.organization_id == org_id,
        )
    )
    rel = rel_q.scalar_one_or_none()
    if rel is None:
        raise NotFoundError(
            message="Client relationship not found.",
            code="NF_CA_003",
        )
    return make_response(_build_client_response(rel))


@router.delete(
    "/clients/{org_id}",
    response_model=ApiResponse[dict],
    summary="Remove a client",
)
async def remove_client(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    rel_q = await db.execute(
        select(CAClientRelationship).where(
            CAClientRelationship.ca_firm_id == ca_firm.id,
            CAClientRelationship.organization_id == org_id,
            CAClientRelationship.status == CAClientStatus.active,
        )
    )
    rel = rel_q.scalar_one_or_none()
    if rel is None:
        raise NotFoundError(
            message="Active client relationship not found.",
            code="NF_CA_003",
        )

    rel.status = CAClientStatus.removed

    db.add(AuditLog(
        action="ca_client_removed",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="ca_client_relationship",
        resource_id=rel.id,
        metadata_json={"removed_org_id": str(org_id)},
    ))

    await db.commit()
    return make_response({"message": "Client removed successfully."})


# ---------------------------------------------------------------------------
# Commissions
# ---------------------------------------------------------------------------


@router.get(
    "/commissions",
    response_model=ApiResponse[list[ReferralCommissionResponse]],
    summary="List referral commissions",
)
async def list_commissions(
    commission_status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[ReferralCommissionResponse]]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    q = select(ReferralCommission).where(ReferralCommission.ca_firm_id == ca_firm.id)
    if commission_status in ("pending", "paid", "cancelled"):
        q = q.where(ReferralCommission.status == ReferralCommissionStatus(commission_status))

    result = await db.execute(q.order_by(ReferralCommission.created_at.desc()).limit(100))
    commissions = [_build_commission_response(c) for c in result.scalars().all()]
    return make_response(commissions)


@router.get(
    "/commissions/summary",
    response_model=ApiResponse[CommissionSummary],
    summary="Commission aggregates",
)
async def commission_summary(
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[CommissionSummary]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)
    firm_id = ca_firm.id

    async def _sum(status_val: ReferralCommissionStatus) -> Decimal:
        r = await db.execute(
            select(func.coalesce(func.sum(ReferralCommission.commission_amount), 0)).where(
                ReferralCommission.ca_firm_id == firm_id,
                ReferralCommission.status == status_val,
            )
        )
        return Decimal(str(r.scalar() or 0))

    async def _count(status_val: ReferralCommissionStatus) -> int:
        r = await db.execute(
            select(func.count()).where(
                ReferralCommission.ca_firm_id == firm_id,
                ReferralCommission.status == status_val,
            )
        )
        return r.scalar() or 0

    return make_response(CommissionSummary(
        total_pending=await _sum(ReferralCommissionStatus.pending),
        total_paid=await _sum(ReferralCommissionStatus.paid),
        total_cancelled=await _sum(ReferralCommissionStatus.cancelled),
        count_pending=await _count(ReferralCommissionStatus.pending),
        count_paid=await _count(ReferralCommissionStatus.paid),
    ))


@router.post(
    "/commissions/{commission_id}/mark-paid",
    response_model=ApiResponse[ReferralCommissionResponse],
    summary="Mark a commission as paid",
)
async def mark_commission_paid(
    commission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[ReferralCommissionResponse]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    c_q = await db.execute(
        select(ReferralCommission).where(
            ReferralCommission.id == commission_id,
            ReferralCommission.ca_firm_id == ca_firm.id,
        )
    )
    commission = c_q.scalar_one_or_none()
    if commission is None:
        raise NotFoundError(
            message="Commission record not found.",
            code="NF_CA_004",
        )
    if commission.status != ReferralCommissionStatus.pending:
        raise ValidationError(
            message="Only pending commissions can be marked as paid.",
            code="VAL_CA_002",
        )

    commission.status = ReferralCommissionStatus.paid
    commission.payout_date = datetime.now(tz=timezone.utc)

    await db.commit()
    await db.refresh(commission)
    return make_response(_build_commission_response(commission))


# ---------------------------------------------------------------------------
# Bulk Report
# ---------------------------------------------------------------------------


@router.get(
    "/me/report",
    summary="Download bulk CA client report PDF",
)
async def download_bulk_report(
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> object:
    from fastapi.responses import Response

    from app.services.pdf_generator import generate_bulk_ca_report

    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    # Fetch all active clients + their recent commissions
    rel_q = await db.execute(
        select(CAClientRelationship).where(
            CAClientRelationship.ca_firm_id == ca_firm.id,
            CAClientRelationship.status == CAClientStatus.active,
        ).order_by(CAClientRelationship.created_at.desc())
    )
    relationships = rel_q.scalars().all()

    com_q = await db.execute(
        select(ReferralCommission)
        .where(ReferralCommission.ca_firm_id == ca_firm.id)
        .order_by(ReferralCommission.created_at.desc())
        .limit(200)
    )
    commissions = com_q.scalars().all()

    clients_data = [
        {
            "name": r.organization.business_name,
            "gstin": r.organization.gstin,
            "commission_rate": float(r.referral_commission_rate),
            "added_on": r.created_at.strftime("%d/%m/%Y"),
        }
        for r in relationships
    ]

    commissions_data = [
        {
            "org_name": c.organization.business_name,
            "amount": float(c.commission_amount),
            "rate": float(c.commission_rate),
            "status": c.status.value,
            "date": c.created_at.strftime("%d/%m/%Y"),
        }
        for c in commissions
    ]

    pdf_bytes = generate_bulk_ca_report(
        firm_name=ca_firm.firm_name,
        primary_ca_name=ca_firm.primary_ca_name,
        icai_membership_number=ca_firm.icai_membership_number,
        city=ca_firm.city,
        state=ca_firm.state,
        total_clients=ca_firm.total_clients,
        total_earnings=float(ca_firm.total_referral_earnings),
        clients=clients_data,
        commissions=commissions_data,
        generated_at=datetime.now(tz=timezone.utc),
    )

    filename = f"ca_report_{ca_firm.firm_name.replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# White-label Branding (public)
# ---------------------------------------------------------------------------


@router.get(
    "/branding/{subdomain}",
    response_model=ApiResponse[BrandingResponse],
    summary="Get white-label branding by subdomain (public)",
)
async def get_branding(
    subdomain: str,
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[BrandingResponse]:
    result = await db.execute(
        select(CAFirm).where(
            CAFirm.white_label_subdomain == subdomain.lower(),
            CAFirm.is_active.is_(True),
        )
    )
    ca_firm = result.scalar_one_or_none()
    if ca_firm is None:
        raise NotFoundError(
            message=f"No CA firm found for subdomain '{subdomain}'.",
            code="NF_CA_005",
        )
    return make_response(BrandingResponse(
        firm_name=ca_firm.firm_name,
        primary_ca_name=ca_firm.primary_ca_name,
        city=ca_firm.city,
        state=ca_firm.state,
        primary_color=ca_firm.primary_color,
        logo_s3_key=ca_firm.logo_s3_key,
        white_label_subdomain=ca_firm.white_label_subdomain or "",
    ))
