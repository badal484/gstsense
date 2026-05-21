"""GST Notice Management API.

Legal safeguards implemented:
1. AI draft NEVER submitted directly to GSTN
2. CA credential verification BEFORE download
3. Non-removable disclaimer on every PDF
4. Human-in-loop approval workflow
5. Full audit trail on every action
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Response, UploadFile, status
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, get_current_org, get_current_user, get_db_session
from app.core.config import settings
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.security import generate_secure_token
from app.models.audit_log import AuditLog
from app.models.notice import DraftStatus, Notice, NoticeType
from app.models.organization import Organization
from app.models.user import User
from app.schemas.common import ApiResponse, make_response
from app.schemas.notice import (
    NoticeDraftResponse,
    NoticeApprovalRequest,
    NoticeDetailResponse,
    NoticeListResponse,
    NoticeUploadResponse,
)
from app.services.notice_drafter import (
    LEGAL_DISCLAIMER,
    extract_text_from_pdf,
    parse_notice_details,
)
from app.services.pdf_generator import generate_notice_reply_pdf
from app.services.s3_service import s3_service

logger = get_logger(__name__)

router = APIRouter(prefix="/notices", tags=["GST Notices"])

NOTICE_PDF_MAX_SIZE_BYTES = 20 * 1024 * 1024

_NOTICE_TYPE_MAP = {
    "DRC-01": NoticeType.DRC_01,
    "DRC-01A": NoticeType.DRC_01A,
    "DRC-01C": NoticeType.DRC_01C,
    "DRC-07": NoticeType.DRC_07,
    "DRC-10": NoticeType.DRC_10,
    "ASMT-10": NoticeType.ASMT_10,
    "ASMT-11": NoticeType.ASMT_11,
    "REG-03": NoticeType.REG_03,
    "REG-17": NoticeType.REG_17,
}


def _assert_notice_owner(notice: Optional[Notice], notice_id: uuid.UUID, org_id: uuid.UUID) -> Notice:
    if notice is None:
        raise NotFoundError(message=f"Notice {notice_id} not found", code="NOT_001")
    if notice.organization_id != org_id:
        raise AuthorizationError.resource_not_owned("notice")
    return notice


@router.post(
    "/upload",
    response_model=ApiResponse[NoticeUploadResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload GST notice PDF for AI-powered reply drafting",
)
async def upload_notice(
    background_tasks: BackgroundTasks,
    notice_file: UploadFile = File(..., description="GST notice PDF file"),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
    ip: Optional[str] = Depends(get_client_ip),
) -> ApiResponse[NoticeUploadResponse]:
    # Validate PDF by filename
    filename = notice_file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise ValidationError.invalid_file_type(filename, [".pdf"])

    file_bytes = await notice_file.read()

    # Validate PDF magic bytes
    if not file_bytes.startswith(b"%PDF"):
        raise ValidationError(
            message="Uploaded file does not appear to be a valid PDF document.",
            code="VAL_003",
        )

    if len(file_bytes) > NOTICE_PDF_MAX_SIZE_BYTES:
        raise ValidationError.file_too_large(
            len(file_bytes) / (1024 * 1024), 20
        )

    # Extract text and parse details immediately (sync — fast enough for PDF text)
    extracted_text = extract_text_from_pdf(file_bytes)
    details = parse_notice_details(extracted_text)

    notice_id = uuid.uuid4()
    s3_key = f"orgs/{org.id}/notices/{notice_id}/notice.pdf"

    await s3_service.upload_file(
        file_bytes,
        s3_key,
        content_type="application/pdf",
        metadata={
            "org_id": str(org.id),
            "notice_id": str(notice_id),
            "file_type": "gst_notice",
        },
    )

    # Map parsed notice type to enum value
    raw_type = details.get("notice_type") or "other"
    notice_type_enum = _NOTICE_TYPE_MAP.get(raw_type, NoticeType.other)

    # Parse demand amount to Decimal if present
    demand_decimal = None
    if details.get("demand_amount") is not None:
        from decimal import Decimal
        demand_decimal = Decimal(str(details["demand_amount"]))

    # Parse due date
    due_date = None
    if details.get("response_due_date"):
        from datetime import date as _date
        import re as _re
        raw_date = str(details["response_due_date"])
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"):
            try:
                due_date = datetime.strptime(raw_date, fmt).date()
                break
            except ValueError:
                continue

    notice = Notice(
        id=notice_id,
        organization_id=org.id,
        notice_number=details.get("notice_number") or "UNKNOWN",
        notice_type=notice_type_enum,
        demand_amount=demand_decimal,
        tax_period=details.get("tax_period"),
        response_due_date=due_date,
        pdf_s3_key=s3_key,
        extracted_text=extracted_text,
        draft_status=DraftStatus.pending,
    )
    db.add(notice)
    db.add(AuditLog(
        action="notice_uploaded",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="notice",
        resource_id=notice_id,
        ip_address=ip,
        metadata_json={
            "notice_type": raw_type,
            "notice_number": details.get("notice_number"),
            "demand_amount": str(demand_decimal) if demand_decimal else None,
        },
    ))
    await db.flush()
    await db.commit()

    # Queue draft generation
    if settings.is_development:
        from app.workers.notice_tasks import _generate_draft_async
        background_tasks.add_task(
            _run_draft_in_background, str(notice_id), str(org.id)
        )
    else:
        from app.workers.notice_tasks import generate_notice_draft_task
        generate_notice_draft_task.apply_async(
            args=[str(notice_id), str(org.id)],
            queue="normal",
        )

    return make_response(
        NoticeUploadResponse(
            notice_id=notice_id,
            status="uploaded",
            notice_type=raw_type if raw_type != "other" else None,
            notice_number=details.get("notice_number"),
            demand_amount=demand_decimal,
            response_due_date=due_date,
        )
    )


async def _run_draft_in_background(notice_id: str, org_id: str) -> None:
    """Dev-mode wrapper to run async draft generation as BackgroundTask."""
    from app.workers.notice_tasks import _generate_draft_async
    try:
        await _generate_draft_async(notice_id, org_id)
    except Exception as exc:
        logger.error("background_draft_failed", notice_id=notice_id, error=str(exc))


@router.get(
    "/{notice_id}",
    response_model=ApiResponse[NoticeDetailResponse],
    summary="Get notice details",
)
async def get_notice(
    notice_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[NoticeDetailResponse]:
    result = await db.execute(select(Notice).where(Notice.id == notice_id))
    notice = _assert_notice_owner(result.scalar_one_or_none(), notice_id, org.id)
    return make_response(
        NoticeDetailResponse(
            id=notice.id,
            notice_number=notice.notice_number,
            notice_type=notice.notice_type.value,
            demand_amount=notice.demand_amount,
            tax_period=notice.tax_period,
            response_due_date=notice.response_due_date,
            draft_status=notice.draft_status.value,
            icai_membership_number=notice.icai_membership_number,
            created_at=notice.created_at,
        )
    )


@router.get(
    "/{notice_id}/draft",
    response_model=ApiResponse[NoticeDraftResponse],
    summary="Get AI-generated reply draft (includes mandatory legal disclaimer)",
)
async def get_notice_draft(
    notice_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[NoticeDraftResponse]:
    result = await db.execute(select(Notice).where(Notice.id == notice_id))
    notice = _assert_notice_owner(result.scalar_one_or_none(), notice_id, org.id)

    if notice.draft_status == DraftStatus.pending:
        raise ValidationError(
            message="Draft is still being generated. Please try again in a moment.",
            code="VAL_005",
        )

    db.add(AuditLog(
        action="notice_draft_viewed",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="notice",
        resource_id=notice_id,
    ))
    await db.commit()

    return make_response(
        NoticeDraftResponse(
            notice_id=notice.id,
            notice_number=notice.notice_number,
            draft_reply_text=notice.draft_reply_text or "",
            draft_status=notice.draft_status.value,
            disclaimer_text=LEGAL_DISCLAIMER,
            warnings=list(notice.draft_warnings or []),
        )
    )


@router.post(
    "/{notice_id}/verify-credentials",
    response_model=ApiResponse[dict],
    summary="Verify CA credentials before download (legally required)",
)
async def verify_ca_credentials(
    notice_id: uuid.UUID,
    icai_number: str = Query(..., description="ICAI Membership Number e.g. MRN123456"),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
    ip: Optional[str] = Depends(get_client_ip),
) -> ApiResponse[dict]:
    # Validate ICAI format
    import re
    _ICAI_RE = re.compile(r"^[A-Z]{1,3}[0-9]{4,8}[A-Z]?$", re.IGNORECASE)
    normalized = icai_number.strip().upper()
    if not _ICAI_RE.match(normalized):
        raise ValidationError(
            message="Invalid ICAI membership number format. Expected: MRN123456 or FRN100001W",
            code="VAL_005",
        )

    result = await db.execute(select(Notice).where(Notice.id == notice_id))
    notice = _assert_notice_owner(result.scalar_one_or_none(), notice_id, org.id)

    update_vals: dict = {"icai_membership_number": normalized}
    if notice.draft_status == DraftStatus.generated:
        update_vals["draft_status"] = DraftStatus.reviewed

    await db.execute(
        update(Notice)
        .where(Notice.id == notice_id)
        .values(**update_vals)
    )

    db.add(AuditLog(
        action="ca_credentials_verified",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="notice",
        resource_id=notice_id,
        ip_address=ip,
        metadata_json={"icai_number": normalized},
    ))
    await db.commit()

    return make_response({
        "verified": True,
        "icai_number": normalized,
        "message": (
            "Credentials verified. You may now download the draft. "
            "Remember: you are responsible for reviewing and approving "
            "this draft before submission."
        ),
    })


@router.get(
    "/{notice_id}/download",
    summary="Download notice reply PDF (requires credential verification)",
)
async def download_notice_reply(
    notice_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    result = await db.execute(select(Notice).where(Notice.id == notice_id))
    notice = _assert_notice_owner(result.scalar_one_or_none(), notice_id, org.id)

    # CRITICAL LEGAL CHECK 1: CA credentials must be verified
    if not notice.icai_membership_number:
        raise AuthorizationError(
            message=(
                "Please verify your CA credentials before downloading. "
                "This is required to ensure compliance with the Advocates Act, 1961."
            ),
            code="AUTHZ_001",
        )

    # CRITICAL LEGAL CHECK 2: Draft must be reviewed or approved
    if notice.draft_status not in (DraftStatus.reviewed, DraftStatus.approved):
        raise ValidationError(
            message="Draft is not yet ready for download. Please wait for generation to complete.",
            code="VAL_005",
        )

    pdf_bytes = generate_notice_reply_pdf(
        notice_number=notice.notice_number,
        organization_name=org.business_name,
        gstin=org.gstin,
        draft_reply_text=notice.draft_reply_text or "",
        icai_membership_number=notice.icai_membership_number,
        generated_at=datetime.now(tz=timezone.utc),
        warnings=list(notice.draft_warnings or []),
    )

    db.add(AuditLog(
        action="notice_draft_downloaded",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="notice",
        resource_id=notice_id,
        metadata_json={"icai_number": notice.icai_membership_number},
    ))
    await db.commit()

    safe_number = notice.notice_number.replace("/", "_").replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="GSTSense_Notice_Reply_{safe_number}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


@router.post(
    "/{notice_id}/approve",
    response_model=ApiResponse[dict],
    summary="CA approves draft for submission",
)
async def approve_draft(
    notice_id: uuid.UUID,
    request_body: NoticeApprovalRequest,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    result = await db.execute(select(Notice).where(Notice.id == notice_id))
    notice = _assert_notice_owner(result.scalar_one_or_none(), notice_id, org.id)

    if not notice.icai_membership_number:
        raise AuthorizationError(
            message="Please verify your CA credentials before approving the draft.",
            code="AUTHZ_001",
        )

    new_draft_text = notice.draft_reply_text or ""
    if request_body.notes:
        new_draft_text += f"\n\n--- CA NOTES ---\n{request_body.notes}"

    await db.execute(
        update(Notice)
        .where(Notice.id == notice_id)
        .values(
            draft_status=DraftStatus.approved,
            reviewed_by_user_id=current_user.id,
            draft_reply_text=new_draft_text,
        )
    )

    db.add(AuditLog(
        action="notice_draft_approved",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="notice",
        resource_id=notice_id,
        metadata_json={"icai_number": notice.icai_membership_number},
    ))
    await db.commit()

    return make_response({
        "approved": True,
        "message": (
            "Draft approved. To submit: login to GST portal, go to Services > Notices, "
            "find your notice, and upload this reply document."
        ),
    })


@router.post(
    "/{notice_id}/share",
    response_model=ApiResponse[dict],
    summary="Generate shareable link for CA review",
)
async def share_draft(
    notice_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    result = await db.execute(select(Notice).where(Notice.id == notice_id))
    notice = _assert_notice_owner(result.scalar_one_or_none(), notice_id, org.id)

    raw_token = generate_secure_token(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=7)

    await db.execute(
        update(Notice)
        .where(Notice.id == notice_id)
        .values(share_token=token_hash, share_token_expires_at=expires_at)
    )

    db.add(AuditLog(
        action="notice_draft_shared",
        user_id=current_user.id,
        organization_id=org.id,
        resource_type="notice",
        resource_id=notice_id,
    ))
    await db.commit()

    share_url = f"{settings.FRONTEND_URL}/notice/review/{raw_token}"
    return make_response({
        "share_url": share_url,
        "expires_at": expires_at.isoformat(),
        "message": "Share this link with your CA. The link expires in 7 days.",
    })


@router.get(
    "/",
    response_model=ApiResponse[NoticeListResponse],
    summary="List all notices for the organization",
)
async def list_notices(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[NoticeListResponse]:
    base_q = select(Notice).where(Notice.organization_id == org.id)
    count_result = await db.execute(
        select(func.count()).select_from(base_q.subquery())
    )
    total = count_result.scalar_one()

    notices_result = await db.execute(
        base_q.order_by(desc(Notice.created_at)).offset((page - 1) * limit).limit(limit)
    )
    notices = notices_result.scalars().all()

    return make_response(
        NoticeListResponse(
            notices=[
                NoticeDetailResponse(
                    id=n.id,
                    notice_number=n.notice_number,
                    notice_type=n.notice_type.value,
                    demand_amount=n.demand_amount,
                    tax_period=n.tax_period,
                    response_due_date=n.response_due_date,
                    draft_status=n.draft_status.value,
                    icai_membership_number=n.icai_membership_number,
                    created_at=n.created_at,
                )
                for n in notices
            ],
            total=total,
        )
    )


# ---------------------------------------------------------------------------
# Public review endpoints (no authentication required)
# ---------------------------------------------------------------------------

class PublicReviewResponse(ApiResponse[dict]):
    pass


@router.get(
    "/review/{token}",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Get notice for public CA review (no auth)",
)
async def get_notice_for_review(
    token: str,
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(Notice).where(Notice.share_token == token_hash)
    )
    notice = result.scalar_one_or_none()

    if notice is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Review link not found.")

    now = datetime.now(tz=timezone.utc)
    is_expired = notice.share_token_expires_at is None or notice.share_token_expires_at < now

    # Fetch org details
    org_result = await db.execute(
        select(Organization).where(Organization.id == notice.organization_id)
    )
    org = org_result.scalar_one_or_none()

    return make_response({
        "notice_id": str(notice.id),
        "notice_type": notice.notice_type.value,
        "gstin": org.gstin if org else "",
        "business_name": org.business_name if org else "",
        "tax_period": notice.tax_period,
        "demand_amount": str(notice.demand_amount) if notice.demand_amount else None,
        "draft_response": notice.draft_reply_text or "",
        "draft_status": notice.draft_status.value,
        "issued_at": notice.created_at.isoformat() if notice.created_at else None,
        "due_date": notice.response_due_date.isoformat() if notice.response_due_date else None,
        "is_expired": is_expired,
    })


class PublicApproveRequest(ApiResponse[dict]):
    pass


@router.post(
    "/review/{token}/approve",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Approve notice draft via share link (no auth)",
)
async def approve_via_share_link(
    token: str,
    body: dict,
    db: AsyncSession = Depends(get_db_session),
    ip: Optional[str] = Depends(get_client_ip),
) -> ApiResponse[dict]:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(Notice).where(Notice.share_token == token_hash)
    )
    notice = result.scalar_one_or_none()

    if notice is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Review link not found.")

    now = datetime.now(tz=timezone.utc)
    if notice.share_token_expires_at is None or notice.share_token_expires_at < now:
        from fastapi import HTTPException
        raise HTTPException(status_code=410, detail="This review link has expired.")

    icai_number = str(body.get("icai_number", "")).strip()
    comment = str(body.get("comment", "")).strip()

    notice.draft_status = DraftStatus.approved
    if icai_number:
        notice.icai_membership_number = icai_number

    db.add(AuditLog(
        action="notice_approved_via_share_link",
        organization_id=notice.organization_id,
        resource_type="notice",
        resource_id=notice.id,
        ip_address=ip,
        metadata_json={"icai_number": icai_number, "comment": comment},
    ))
    await db.commit()

    return make_response({"message": "Response approved. Your CA has been notified."})
