import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile, status
from app.workers.scan_tasks import _mark_scan_failed, _process_scan_async
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, get_current_org, get_current_user, get_db_session
from app.core.config import settings
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.mismatch import Mismatch
from app.models.organization import Organization
from app.models.scan import Scan, ScanStatus
from app.models.user import User
from app.schemas.common import ApiResponse, make_response
from app.schemas.scan import (
    MismatchResponse,
    ScanListItem,
    ScanListResponse,
    ScanPreviewResponse,
    ScanReportResponse,
    ScanStatusResponse,
    ScanUploadResponse,
)
from app.services.parser import validate_excel_bytes
from app.services.s3_service import s3_service
from app.workers.scan_tasks import process_scan_task

logger = get_logger(__name__)

router = APIRouter(prefix="/scans", tags=["Scans"])

MAX_FILE_SIZE_BYTES = settings.max_file_size_bytes
_ALLOWED_EXTENSIONS = {".xlsx", ".xls"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_upload_file(file: UploadFile) -> None:
    """Raise ValidationError if the filename extension is not an Excel type."""
    if not file.filename:
        raise ValidationError.invalid_file_type("(no filename)", list(_ALLOWED_EXTENSIONS))
    name = file.filename.lower()
    if not any(name.endswith(ext) for ext in _ALLOWED_EXTENSIONS):
        raise ValidationError.invalid_file_type(file.filename, list(_ALLOWED_EXTENSIONS))


def _assert_scan_owner(scan: Optional[Scan], scan_id: uuid.UUID, org_id: uuid.UUID) -> Scan:
    """Return *scan* or raise the appropriate 404/403."""
    if scan is None:
        raise NotFoundError.scan(str(scan_id))
    if scan.organization_id != org_id:
        raise AuthorizationError.resource_not_owned("scan")
    return scan


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/upload",
    response_model=ApiResponse[ScanUploadResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload GSTR files for scanning",
    description="Upload GSTR-1 and GSTR-3B Excel files to detect mismatches",
)
async def upload_scan(
    background_tasks: BackgroundTasks,
    gstr1_file: UploadFile = File(..., description="GSTR-1 Excel file"),
    gstr3b_file: UploadFile = File(..., description="GSTR-3B Excel file"),
    scan_month: str = Form(
        default="",
        description="Filing month in YYYY-MM format (defaults to current month)",
    ),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
    ip: Optional[str] = Depends(get_client_ip),
) -> ApiResponse[ScanUploadResponse]:
    # ---- 1 & 2. Validate files ----
    _validate_upload_file(gstr1_file)
    _validate_upload_file(gstr3b_file)

    gstr1_bytes = await gstr1_file.read()
    gstr3b_bytes = await gstr3b_file.read()

    max_bytes = MAX_FILE_SIZE_BYTES
    if len(gstr1_bytes) > max_bytes:
        raise ValidationError.file_too_large(
            len(gstr1_bytes) / (1024 * 1024), settings.MAX_FILE_SIZE_MB
        )
    if len(gstr3b_bytes) > max_bytes:
        raise ValidationError.file_too_large(
            len(gstr3b_bytes) / (1024 * 1024), settings.MAX_FILE_SIZE_MB
        )

    # Validate actual bytes (not just extension) to block non-Excel uploads.
    validate_excel_bytes(gstr1_bytes)
    validate_excel_bytes(gstr3b_bytes)

    # ---- 3. Invoice limit check ----
    if org.is_invoice_limit_reached:
        raise AuthorizationError.plan_upgrade_required(
            required_plan="smb",
            current_plan=org.plan.value,
        )

    # ---- 4. Derive scan_month ----
    if not scan_month:
        scan_month = datetime.now(tz=timezone.utc).strftime("%Y-%m")

    # ---- 5 & 6. Upload to S3 ----
    scan_id = uuid.uuid4()
    gstr1_key = s3_service.build_scan_gstr1_key(str(org.id), str(scan_id))
    gstr3b_key = s3_service.build_scan_gstr3b_key(str(org.id), str(scan_id))

    await s3_service.upload_file(
        gstr1_bytes,
        gstr1_key,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        metadata={"org_id": str(org.id), "scan_id": str(scan_id), "file_type": "gstr1"},
    )
    await s3_service.upload_file(
        gstr3b_bytes,
        gstr3b_key,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        metadata={"org_id": str(org.id), "scan_id": str(scan_id), "file_type": "gstr3b"},
    )

    # ---- 7. Create Scan record ----
    scan = Scan(
        id=scan_id,
        organization_id=org.id,
        scan_month=scan_month,
        gstr1_s3_key=gstr1_key,
        gstr3b_s3_key=gstr3b_key,
        status=ScanStatus.uploaded,
    )
    db.add(scan)

    # ---- 8. Audit log ----
    db.add(
        AuditLog(
            action="scan_uploaded",
            user_id=current_user.id,
            organization_id=org.id,
            resource_type="scan",
            resource_id=scan_id,
            ip_address=ip,
        )
    )

    # ---- 9. Commit ----
    await db.flush()
    await db.commit()

    logger.info(
        "scan_uploaded",
        scan_id=str(scan_id),
        org_id=str(org.id),
        scan_month=scan_month,
    )

    # ---- 10. Queue task (direct background task in dev, Celery in prod) ----
    if settings.is_development:
        async def _dev_task() -> None:
            try:
                await _process_scan_async(str(scan_id), str(org.id), "dev-task")
            except Exception as exc:
                logger.error("dev_scan_task_failed", scan_id=str(scan_id), error=str(exc))
                try:
                    await _mark_scan_failed(str(scan_id), str(exc)[:1000])
                except Exception:
                    pass
        background_tasks.add_task(_dev_task)
    else:
        process_scan_task.apply_async(
            args=[str(scan_id), str(org.id)],
            queue="normal",
        )

    return make_response(
        ScanUploadResponse(
            scan_id=scan_id,
            status=ScanStatus.uploaded,
        )
    )


@router.get(
    "/{scan_id}/status",
    response_model=ApiResponse[ScanStatusResponse],
    summary="Get scan processing status",
)
async def get_scan_status(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[ScanStatusResponse]:
    cache_key = f"scan_status:{scan_id}"
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        cached_status = await r.get(cache_key)
    except Exception:
        cached_status = None
    finally:
        await r.aclose()

    if cached_status:
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = _assert_scan_owner(result.scalar_one_or_none(), scan_id, org.id)
    else:
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = _assert_scan_owner(result.scalar_one_or_none(), scan_id, org.id)
        try:
            r2 = aioredis.from_url(settings.REDIS_URL)
            await r2.setex(cache_key, 2, scan.status.value)
            await r2.aclose()
        except Exception:
            pass

    return make_response(
        ScanStatusResponse(
            scan_id=scan.id,
            status=scan.status,
            created_at=scan.created_at,
            completed_at=scan.completed_at,
            processing_duration_seconds=scan.processing_duration_seconds,
        )
    )


@router.get(
    "/{scan_id}/preview",
    response_model=ApiResponse[ScanPreviewResponse],
    summary="Get scan preview (free)",
    description="Returns mismatch count and rupee risk. Full report requires payment.",
)
async def get_scan_preview(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[ScanPreviewResponse]:
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = _assert_scan_owner(result.scalar_one_or_none(), scan_id, org.id)

    if scan.status != ScanStatus.completed:
        raise ValidationError(
            message="Scan is still processing. Please try again shortly.",
            code="VAL_005",
        )

    # Fetch first 3 mismatches for the free preview
    preview_rows = await db.execute(
        select(Mismatch)
        .where(Mismatch.scan_id == scan_id)
        .order_by(desc(Mismatch.rupee_difference))
        .limit(3)
    )
    preview_mismatches = preview_rows.scalars().all()

    db.add(
        AuditLog(
            action="report_preview_viewed",
            user_id=current_user.id,
            organization_id=org.id,
            resource_type="scan",
            resource_id=scan_id,
        )
    )
    await db.commit()

    return make_response(
        ScanPreviewResponse(
            scan_id=scan.id,
            total_mismatches=scan.total_mismatches,
            total_invoices_scanned=scan.total_invoices_scanned,
            total_rupee_risk=scan.total_rupee_risk,
            is_paid=scan.is_paid,
            scan_month=scan.scan_month,
            preview_mismatches=[MismatchResponse.model_validate(m) for m in preview_mismatches],
        )
    )


@router.get(
    "/{scan_id}/report",
    response_model=ApiResponse[ScanReportResponse],
    summary="Get full scan report (requires payment)",
)
async def get_scan_report(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[ScanReportResponse]:
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = _assert_scan_owner(result.scalar_one_or_none(), scan_id, org.id)

    if not scan.is_paid:
        raise AuthorizationError.scan_not_paid(str(scan_id))

    mismatches_result = await db.execute(
        select(Mismatch)
        .where(Mismatch.scan_id == scan_id)
        .order_by(desc(Mismatch.rupee_difference))
    )
    mismatches = mismatches_result.scalars().all()

    db.add(
        AuditLog(
            action="report_viewed",
            user_id=current_user.id,
            organization_id=org.id,
            resource_type="scan",
            resource_id=scan_id,
        )
    )
    await db.commit()

    unique_suppliers = len({m.supplier_gstin for m in mismatches})

    return make_response(
        ScanReportResponse(
            scan_id=scan.id,
            scan_month=scan.scan_month,
            total_invoices_scanned=scan.total_invoices_scanned,
            total_mismatches=scan.total_mismatches,
            total_rupee_risk=scan.total_rupee_risk,
            total_unique_suppliers=unique_suppliers,
            created_at=scan.created_at,
            warnings=[],
            mismatches=[MismatchResponse.model_validate(m) for m in mismatches],
        )
    )


@router.get(
    "/{scan_id}/download",
    summary="Download PDF report",
    description="Download mismatch report as PDF. Requires payment.",
)
async def download_scan_report(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = _assert_scan_owner(result.scalar_one_or_none(), scan_id, org.id)

    if not scan.is_paid:
        raise AuthorizationError.scan_not_paid(str(scan_id))

    if not scan.pdf_s3_key:
        logger.info("pdf_not_ready_queuing_generation", scan_id=str(scan_id))
        message = "PDF is being generated. Please try again in a moment."
        return {
            "status": "pending",
            "message": message,
            "data": {"status": "pending", "message": message},
        }

    download_url = await s3_service.generate_presigned_url(
        s3_key=scan.pdf_s3_key,
        expiry_seconds=settings.AWS_S3_PRESIGN_EXPIRY,
        filename=f"gst_report_{scan.scan_month}.pdf",
    )

    db.add(
        AuditLog(
            action="report_downloaded",
            user_id=current_user.id,
            organization_id=org.id,
            resource_type="scan",
            resource_id=scan_id,
        )
    )
    await db.commit()

    # Backward-compatible response:
    # - top-level `download_url` supports existing frontend code.
    # - `data.download_url` supports standard API response parsing.
    return {
        "status": "success",
        "data": {"download_url": download_url},
        "download_url": download_url,
    }


@router.get(
    "/",
    response_model=ApiResponse[ScanListResponse],
    summary="List all scans for organization",
)
async def list_scans(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    status_filter: Optional[ScanStatus] = Query(default=None),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[ScanListResponse]:
    base_query = select(Scan).where(Scan.organization_id == org.id)

    if status_filter is not None:
        base_query = base_query.where(Scan.status == status_filter)

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    # Paginated results
    scans_result = await db.execute(
        base_query.order_by(desc(Scan.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
    )
    scans = scans_result.scalars().all()

    return make_response(
        ScanListResponse(
            scans=[ScanListItem.model_validate(s) for s in scans],
            total=total,
            page=page,
            limit=limit,
        )
    )
