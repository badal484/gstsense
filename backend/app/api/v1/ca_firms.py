"""CA Firm White-Label System API endpoints."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel as _BM
from app.api.deps import get_current_user, get_db_session, require_plan
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.bank_details import CABankDetails
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
@router.post(
    "/me/clients",
    response_model=ApiResponse[CAClientResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add client organization by GSTIN (me prefix)",
)
async def add_client(
    body: AddClientRequest,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[CAClientResponse]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    # Find the organization by GSTIN (case-insensitive)
    org_q = await db.execute(
        select(Organization).where(func.upper(Organization.gstin) == body.gstin.upper())
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
@router.get(
    "/me/clients",
    response_model=ApiResponse[list[CAClientResponse]],
    summary="List all clients (me prefix)",
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
@router.get(
    "/me/clients/{org_id}",
    response_model=ApiResponse[CAClientResponse],
    summary="Get client details (me prefix)",
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
@router.delete(
    "/me/clients/{org_id}",
    response_model=ApiResponse[dict],
    summary="Remove a client (me prefix)",
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
    organization_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[ReferralCommissionResponse]]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    q = select(ReferralCommission).where(ReferralCommission.ca_firm_id == ca_firm.id)
    if commission_status in ("pending", "paid", "cancelled"):
        q = q.where(ReferralCommission.status == ReferralCommissionStatus(commission_status))
    if organization_id:
        try:
            q = q.where(ReferralCommission.organization_id == uuid.UUID(organization_id))
        except ValueError:
            pass

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


@router.post(
    "/me/report",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue bulk CA client report PDF generation",
)
async def enqueue_bulk_report(
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    from app.workers.report_tasks import generate_bulk_ca_report_task

    ca_firm = await _get_ca_firm_or_404(db, current_user.id)
    task = generate_bulk_ca_report_task.delay(str(ca_firm.id), str(org.id))

    return make_response({
        "job_id": task.id,
        "message": "Report generation started. Poll /me/report/{job_id} for status.",
    })


@router.get(
    "/me/report/{job_id}",
    response_model=ApiResponse[dict],
    summary="Poll bulk CA report generation status",
)
async def get_bulk_report_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
) -> ApiResponse[dict]:
    from celery.result import AsyncResult
    from app.workers.celery_app import celery_app

    result = AsyncResult(job_id, app=celery_app)
    state = result.state

    if state == "PENDING":
        return make_response({"status": "pending"})
    if state == "SUCCESS":
        return make_response({"status": "completed", **result.result})
    if state in ("FAILURE", "REVOKED"):
        return make_response({"status": "failed", "error": str(result.info)})
    return make_response({"status": "processing"})


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
    logo_url: Optional[str] = None
    if ca_firm.logo_s3_key:
        from app.services.s3_service import s3_service
        logo_url = await s3_service.generate_presigned_url(
            s3_key=ca_firm.logo_s3_key,
            expiry_seconds=3600,
        )
    return make_response(BrandingResponse(
        firm_name=ca_firm.firm_name,
        ca_name=ca_firm.primary_ca_name,
        city=ca_firm.city,
        state=ca_firm.state,
        primary_color=ca_firm.primary_color,
        logo_url=logo_url,
        white_label_subdomain=ca_firm.white_label_subdomain or "",
    ))


# ---------------------------------------------------------------------------
# Bank Details endpoints
# ---------------------------------------------------------------------------


class BankDetailsRequest(_BM):
    account_holder_name: str
    account_number: str
    ifsc_code: str
    bank_name: str
    upi_id: Optional[str] = None


class BankDetailsResponse(_BM):
    account_holder_name: str
    account_number_masked: str
    ifsc_code: str
    bank_name: str
    upi_id: Optional[str]

    model_config = {"from_attributes": True}


@router.post(
    "/me/bank-details",
    response_model=ApiResponse[BankDetailsResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add bank details for CA firm payouts",
)
async def create_bank_details(
    body: BankDetailsRequest,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[BankDetailsResponse]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    existing = await db.execute(
        select(CABankDetails).where(CABankDetails.ca_firm_id == ca_firm.id)
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(
            message="Bank details already exist. Use PATCH to update.",
            code="CF_BANK_001",
        )

    record = CABankDetails(
        ca_firm_id=ca_firm.id,
        account_holder_name=body.account_holder_name,
        account_number=body.account_number,
        ifsc_code=body.ifsc_code.upper(),
        bank_name=body.bank_name,
        upi_id=body.upi_id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return make_response(BankDetailsResponse(
        account_holder_name=record.account_holder_name,
        account_number_masked="*" * (len(record.account_number) - 4) + record.account_number[-4:],
        ifsc_code=record.ifsc_code,
        bank_name=record.bank_name,
        upi_id=record.upi_id,
    ))


@router.patch(
    "/me/bank-details",
    response_model=ApiResponse[BankDetailsResponse],
    status_code=status.HTTP_200_OK,
    summary="Update bank details",
)
async def update_bank_details(
    body: BankDetailsRequest,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[BankDetailsResponse]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    result = await db.execute(
        select(CABankDetails).where(CABankDetails.ca_firm_id == ca_firm.id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise NotFoundError(
            message="No bank details found. Use POST to create.",
            code="NF_BANK_001",
        )

    record.account_holder_name = body.account_holder_name
    record.account_number = body.account_number
    record.ifsc_code = body.ifsc_code.upper()
    record.bank_name = body.bank_name
    record.upi_id = body.upi_id

    await db.commit()
    await db.refresh(record)

    return make_response(BankDetailsResponse(
        account_holder_name=record.account_holder_name,
        account_number_masked="*" * (len(record.account_number) - 4) + record.account_number[-4:],
        ifsc_code=record.ifsc_code,
        bank_name=record.bank_name,
        upi_id=record.upi_id,
    ))


@router.get(
    "/me/bank-details",
    response_model=ApiResponse[BankDetailsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get bank details (masked)",
)
async def get_bank_details(
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("ca_firm")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[BankDetailsResponse]:
    ca_firm = await _get_ca_firm_or_404(db, current_user.id)

    result = await db.execute(
        select(CABankDetails).where(CABankDetails.ca_firm_id == ca_firm.id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise NotFoundError(
            message="No bank details found.",
            code="NF_BANK_001",
        )

    return make_response(BankDetailsResponse(
        account_holder_name=record.account_holder_name,
        account_number_masked="*" * (len(record.account_number) - 4) + record.account_number[-4:],
        ifsc_code=record.ifsc_code,
        bank_name=record.bank_name,
        upi_id=record.upi_id,
    ))
