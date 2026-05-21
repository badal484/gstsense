"""Celery task for GST notice reply draft generation."""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from celery import Task
from sqlalchemy import select, update

from app.core.database import celery_db_session
from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.notice import DraftStatus, Notice
from app.models.organization import Organization
from app.services.notice_drafter import (
    draft_notice_reply,
    parse_notice_details,
    validate_draft_citations,
    get_relevant_legal_context,
)
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


def run_async(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="app.workers.notice_tasks.generate_notice_draft_task",
    max_retries=2,
    default_retry_delay=30,
    queue="normal",
)
def generate_notice_draft_task(
    self: Task,
    notice_id: str,
    org_id: str,
) -> dict[str, Any]:
    """Generate AI reply draft for an uploaded GST notice."""
    logger.info("notice_task_started", notice_id=notice_id, task_id=self.request.id)
    try:
        result: dict[str, Any] = run_async(_generate_draft_async(notice_id, org_id))
        return result
    except Exception as exc:
        logger.error("notice_task_failed", notice_id=notice_id, error=str(exc))
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            run_async(_mark_draft_failed(notice_id, str(exc)))
        raise


async def _mark_draft_failed(notice_id: str, error_message: str) -> None:
    async with celery_db_session() as db:
        await db.execute(
            update(Notice)
            .where(Notice.id == uuid.UUID(notice_id))
            .values(
                draft_status=DraftStatus.pending,
                draft_warnings=["Draft generation failed. Please contact support."],
            )
        )
        await db.commit()
    logger.warning("notice_draft_marked_failed", notice_id=notice_id, error=error_message)


async def _generate_draft_async(notice_id: str, org_id: str) -> dict:
    notice_uuid = uuid.UUID(notice_id)

    async with celery_db_session() as db:
        # Load notice
        result = await db.execute(select(Notice).where(Notice.id == notice_uuid))
        notice = result.scalar_one()

        # Load organization
        org_result = await db.execute(
            select(Organization).where(Organization.id == uuid.UUID(org_id))
        )
        org = org_result.scalar_one()

        extracted_text = notice.extracted_text or ""
        notice_details = parse_notice_details(extracted_text)

        # Generate draft via AI → template fallback
        raw_draft = await draft_notice_reply(
            notice_text=extracted_text,
            notice_details=notice_details,
            organization_name=org.business_name,
            gstin=org.gstin,
        )

        # Validate citations against the legal context
        legal_context = get_relevant_legal_context(notice_details, extracted_text)
        cleaned_draft, warnings = validate_draft_citations(raw_draft, legal_context)

        # Persist
        await db.execute(
            update(Notice)
            .where(Notice.id == notice_uuid)
            .values(
                draft_reply_text=cleaned_draft,
                draft_warnings=warnings,
                draft_status=DraftStatus.generated,
            )
        )

        db.add(
            AuditLog(
                action="notice_draft_generated",
                organization_id=uuid.UUID(org_id),
                resource_type="notice",
                resource_id=notice_uuid,
                metadata_json={
                    "notice_type": notice_details.get("notice_type"),
                    "warnings_count": len(warnings),
                },
            )
        )
        await db.commit()

        logger.info(
            "notice_draft_complete",
            notice_id=notice_id,
            warnings=len(warnings),
            draft_chars=len(cleaned_draft),
        )
        return {
            "status": "generated",
            "notice_id": notice_id,
            "warnings_count": len(warnings),
        }
