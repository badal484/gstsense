import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, get_current_org, get_current_user, get_db_session, require_plan
from app.core.config import settings
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.itc_scan import ITCIssueRecord, ITCScan, ITCScanStatus
from app.models.organization import Organization
from app.models.user import User
from app.schemas.common import ApiResponse, make_response
from app.schemas.itc import (
    ITCAnalysisResponse,
    ITCIssueResponse,
    ITCScanUploadResponse,
    ITCSummaryResponse,
)
from app.services.itc_analyzer import ITCIssueType
from app.services.s3_service import s3_service
from app.workers.itc_tasks import _process_itc_async, process_itc_task

logger = get_logger(__name__)

router = APIRouter(prefix="/itc", tags=["ITC Recovery"])

MAX_FILE_SIZE_BYTES = settings.max_file_size_bytes
_ALLOWED_EXTENSIONS = {".xlsx", ".xls"}

_TYPE_ORDER = {
    ITCIssueType.EXCESS_CLAIMED.value: 0,
    ITCIssueType.UNCLAIMED.value: 1,
    ITCIssueType.SUPPLIER_NOT_FILED.value: 2,
    ITCIssueType.RATE_DIFFERENCE.value: 3,
}


def _validate_file(file: UploadFile) -> None:
    if not file.filename:
        raise ValidationError.invalid_file_type("(no filename)", list(_ALLOWED_EXTENSIONS))
    if not any(file.filename.lower().endswith(ext) for ext in _ALLOWED_EXTENSIONS):
        raise ValidationError.invalid_file_type(file.filename, list(_ALLOWED_EXTENSIONS))


def _assert_owner(scan: Optional[ITCScan], scan_id: uuid.UUID, org_id: uuid.UUID) -> ITCScan:
    if scan is None:
        raise NotFoundError(message=f"ITC scan {scan_id} not found", code="NOT_001")
    if scan.organization_id != org_id:
        raise AuthorizationError.resource_not_owned("itc_scan")
    return scan


@router.post(
    "/upload",
    response_model=ApiResponse[ITCScanUploadResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload GSTR-3B and GSTR-2B for ITC analysis",
    description="Requires Growth plan or higher",
)
async def upload_itc_scan(
    background_tasks: BackgroundTasks,
    gstr3b_file: UploadFile = File(...),
    gstr2b_file: UploadFile = File(...),
    scan_month: str = Form(default=""),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("growth")),
    db: AsyncSession = Depends(get_db_session),
    ip: Optional[str] = Depends(get_client_ip),
) -> ApiResponse[ITCScanUploadResponse]:
    _validate_file(gstr3b_file)
    _validate_file(gstr2b_file)

    gstr3b_bytes = await gstr3b_file.read()
    gstr2b_bytes = await gstr2b_file.read()

    if len(gstr3b_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValidationError.file_too_large(len(gstr3b_bytes) / (1024 * 1024), settings.MAX_FILE_SIZE_MB)
    if len(gstr2b_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValidationError.file_too_large(len(gstr2b_bytes) / (1024 * 1024), settings.MAX_FILE_SIZE_MB)

    if not scan_month:
        scan_month = datetime.now(tz=timezone.utc).strftime("%Y-%m")

    itc_scan_id = uuid.uuid4()
    gstr3b_key = f"orgs/{org.id}/itc/{itc_scan_id}/gstr3b.xlsx"
    gstr2b_key = f"orgs/{org.id}/itc/{itc_scan_id}/gstr2b.xlsx"

    await s3_service.upload_file(
        gstr3b_bytes, gstr3b_key,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        metadata={"org_id": str(org.id), "itc_scan_id": str(itc_scan_id), "file_type": "gstr3b"},
    )
    await s3_service.upload_file(
        gstr2b_bytes, gstr2b_key,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        metadata={"org_id": str(org.id), "itc_scan_id": str(itc_scan_id), "file_type": "gstr2b"},
    )

    scan = ITCScan(
        id=itc_scan_id,
        organization_id=org.id,
        scan_month=scan_month,
        gstr3b_s3_key=gstr3b_key,
        gstr2b_s3_key=gstr2b_key,
        status=ITCScanStatus.uploaded,
    )
    db.add(scan)
    db.add(AuditLog(
        action="itc_scan_uploaded",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="itc_scan",
        resource_id=itc_scan_id,
        ip_address=ip,
    ))
    await db.flush()
    await db.commit()

    if settings.is_development:
        background_tasks.add_task(_process_itc_async, str(itc_scan_id), str(org.id), "dev-task")
    else:
        process_itc_task.apply_async(
            args=[str(itc_scan_id), str(org.id)],
            queue="normal",
        )

    return make_response(
        ITCScanUploadResponse(scan_id=itc_scan_id, status="uploaded")
    )


@router.get(
    "/summary/latest",
    response_model=ApiResponse[ITCSummaryResponse],
    summary="Get latest ITC summary for dashboard",
    description="Available on all plans. Shows totals only.",
)
async def get_itc_summary(
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[ITCSummaryResponse]:
    result = await db.execute(
        select(ITCScan)
        .where(ITCScan.organization_id == org.id, ITCScan.status == ITCScanStatus.completed)
        .order_by(desc(ITCScan.created_at))
        .limit(1)
    )
    scan = result.scalar_one_or_none()

    requires_upgrade = org.plan.value not in ("growth", "ca_firm")

    if scan is None:
        return make_response(ITCSummaryResponse(
            total_unclaimed_itc=Decimal("0"),
            total_excess_claimed=Decimal("0"),
            total_at_risk=Decimal("0"),
            issue_count=0,
            requires_upgrade=requires_upgrade,
        ))

    issue_count_result = await db.execute(
        select(func.count()).select_from(
            select(ITCIssueRecord).where(ITCIssueRecord.itc_scan_id == scan.id).subquery()
        )
    )
    issue_count = issue_count_result.scalar_one()

    return make_response(ITCSummaryResponse(
        total_unclaimed_itc=scan.total_unclaimed_itc,
        total_excess_claimed=scan.total_excess_claimed,
        total_at_risk=scan.total_at_risk,
        issue_count=issue_count,
        requires_upgrade=requires_upgrade,
    ))


@router.get(
    "/{itc_scan_id}/status",
    response_model=ApiResponse[dict],
    summary="Get ITC scan status",
)
async def get_itc_scan_status(
    itc_scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    result = await db.execute(select(ITCScan).where(ITCScan.id == itc_scan_id))
    scan = _assert_owner(result.scalar_one_or_none(), itc_scan_id, org.id)
    return make_response({
        "itc_scan_id": str(scan.id),
        "status": scan.status.value,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
    })


@router.get(
    "/{itc_scan_id}/analysis",
    response_model=ApiResponse[ITCAnalysisResponse],
    summary="Get full ITC analysis",
    description="Requires Growth plan",
)
async def get_itc_analysis(
    itc_scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_plan("growth")),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[ITCAnalysisResponse]:
    result = await db.execute(select(ITCScan).where(ITCScan.id == itc_scan_id))
    scan = _assert_owner(result.scalar_one_or_none(), itc_scan_id, org.id)

    if scan.status != ITCScanStatus.completed:
        raise ValidationError(
            message="ITC scan is still processing. Please try again shortly.",
            code="VAL_005",
        )

    issues_result = await db.execute(
        select(ITCIssueRecord)
        .where(ITCIssueRecord.itc_scan_id == itc_scan_id)
        .order_by(ITCIssueRecord.issue_type, desc(ITCIssueRecord.difference))
    )
    issues = issues_result.scalars().all()
    issues_sorted = sorted(
        issues,
        key=lambda i: (_TYPE_ORDER.get(i.issue_type, 9), -i.difference),
    )

    issues_by_type: dict[str, int] = {}
    for issue in issues:
        issues_by_type[issue.issue_type] = issues_by_type.get(issue.issue_type, 0) + 1

    unique_suppliers = len({i.supplier_gstin for i in issues})

    db.add(AuditLog(
        action="itc_analysis_viewed",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="itc_scan",
        resource_id=itc_scan_id,
    ))
    await db.commit()

    return make_response(ITCAnalysisResponse(
        scan_id=scan.id,
        total_invoices_checked=scan.total_invoices_checked,
        total_unique_suppliers=unique_suppliers,
        total_unclaimed_itc=scan.total_unclaimed_itc,
        total_excess_claimed=scan.total_excess_claimed,
        total_at_risk=scan.total_at_risk,
        issues=[
            ITCIssueResponse(
                supplier_gstin=i.supplier_gstin,
                supplier_name=i.supplier_name,
                invoice_number=i.invoice_number,
                invoice_date=i.invoice_date,
                issue_type=ITCIssueType(i.issue_type),
                available_itc=i.available_itc,
                claimed_itc=i.claimed_itc,
                difference=i.difference,
                recommendation=i.recommendation,
            )
            for i in issues_sorted
        ],
        issues_by_type=issues_by_type,
    ))


@router.get(
    "/",
    response_model=ApiResponse[dict],
    summary="List ITC scans",
)
async def list_itc_scans(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    base_q = select(ITCScan).where(ITCScan.organization_id == org.id)
    count_result = await db.execute(
        select(func.count()).select_from(base_q.subquery())
    )
    total = count_result.scalar_one()

    scans_result = await db.execute(
        base_q.order_by(desc(ITCScan.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
    )
    scans = scans_result.scalars().all()

    return make_response({
        "scans": [
            {
                "id": str(s.id),
                "scan_month": s.scan_month,
                "status": s.status.value,
                "total_unclaimed_itc": str(s.total_unclaimed_itc),
                "total_excess_claimed": str(s.total_excess_claimed),
                "total_at_risk": str(s.total_at_risk),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in scans
        ],
        "total": total,
        "page": page,
        "limit": limit,
    })
