import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from celery import Task
from sqlalchemy import select, update

from app.core.database import celery_db_session
from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.itc_scan import ITCScan, ITCScanStatus, ITCIssueRecord
from app.services.itc_analyzer import analyze_itc, parse_gstr2b
from app.services.parser import parse_gstr3b
from app.services.s3_service import s3_service
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
    name="app.workers.itc_tasks.process_itc_task",
    max_retries=3,
    default_retry_delay=60,
    queue="normal",
)
def process_itc_task(self: Task, itc_scan_id: str, org_id: str) -> Any:
    """ITC analysis processing pipeline."""
    logger.info("itc_task_started", itc_scan_id=itc_scan_id, task_id=self.request.id)
    try:
        return run_async(_process_itc_async(itc_scan_id, org_id, self.request.id or ""))
    except Exception as exc:
        logger.error("itc_task_failed", itc_scan_id=itc_scan_id, error=str(exc))
        run_async(_mark_itc_failed(itc_scan_id, str(exc)))
        raise


async def _mark_itc_failed(itc_scan_id: str, error_message: str) -> None:
    async with celery_db_session() as db:
        await db.execute(
            update(ITCScan)
            .where(ITCScan.id == uuid.UUID(itc_scan_id))
            .values(
                status=ITCScanStatus.failed,
                error_message=error_message[:1000],
                completed_at=datetime.now(tz=timezone.utc),
            )
        )
        await db.commit()


async def _process_itc_async(itc_scan_id: str, org_id: str, task_id: str) -> dict:
    scan_uuid = uuid.UUID(itc_scan_id)

    async with celery_db_session() as db:
        # Step 1: Transition to processing
        await db.execute(
            update(ITCScan)
            .where(ITCScan.id == scan_uuid)
            .values(
                status=ITCScanStatus.processing,
                celery_task_id=task_id,
            )
        )
        await db.commit()

        result = await db.execute(select(ITCScan).where(ITCScan.id == scan_uuid))
        scan = result.scalar_one()

        # Step 2 & 3: Download files from S3
        try:
            gstr3b_bytes = await s3_service.download_file(scan.gstr3b_s3_key)
            gstr2b_bytes = await s3_service.download_file(scan.gstr2b_s3_key)
        except Exception as exc:
            logger.error("itc_s3_download_error", itc_scan_id=itc_scan_id, error=str(exc))
            raise

        # Step 4: Parse files
        from app.core.exceptions import ValidationError as GSTValidationError

        try:
            gstr3b_result = parse_gstr3b(gstr3b_bytes)
        except GSTValidationError as exc:
            await _mark_itc_failed(itc_scan_id, exc.message)
            return {"status": "failed", "reason": exc.message}

        try:
            gstr2b_df = parse_gstr2b(gstr2b_bytes)
        except GSTValidationError as exc:
            await _mark_itc_failed(itc_scan_id, exc.message)
            return {"status": "failed", "reason": exc.message}

        # Step 5: Analyse
        analysis = analyze_itc(
            gstr3b_df=gstr3b_result.dataframe,
            gstr2b_df=gstr2b_df,
            warnings=gstr3b_result.warnings,
        )

        # Step 6 & 7: Persist
        await db.execute(
            update(ITCScan)
            .where(ITCScan.id == scan_uuid)
            .values(
                total_invoices_checked=analysis.total_invoices_checked,
                total_unclaimed_itc=analysis.total_unclaimed_itc,
                total_excess_claimed=analysis.total_excess_claimed,
                total_at_risk=analysis.total_at_risk,
            )
        )

        for issue in analysis.issues:
            db.add(
                ITCIssueRecord(
                    itc_scan_id=scan_uuid,
                    supplier_gstin=issue.supplier_gstin,
                    supplier_name=issue.supplier_name,
                    invoice_number=issue.invoice_number,
                    invoice_date=issue.invoice_date,
                    issue_type=issue.issue_type.value,
                    available_itc=issue.available_itc,
                    claimed_itc=issue.claimed_itc,
                    difference=issue.difference,
                    recommendation=issue.recommendation,
                )
            )
        await db.flush()

        # Step 8: Mark completed
        now = datetime.now(tz=timezone.utc)
        await db.execute(
            update(ITCScan)
            .where(ITCScan.id == scan_uuid)
            .values(status=ITCScanStatus.completed, completed_at=now)
        )

        # Step 9: Audit log
        db.add(
            AuditLog(
                action="itc_scan_completed",
                organization_id=uuid.UUID(org_id),
                resource_type="itc_scan",
                resource_id=scan_uuid,
                metadata_json={
                    "total_unclaimed_itc": str(analysis.total_unclaimed_itc),
                    "total_excess_claimed": str(analysis.total_excess_claimed),
                    "issue_count": len(analysis.issues),
                },
            )
        )
        await db.commit()

        logger.info(
            "itc_task_completed",
            itc_scan_id=itc_scan_id,
            issue_count=len(analysis.issues),
            total_unclaimed=str(analysis.total_unclaimed_itc),
        )

        return {
            "status": "completed",
            "itc_scan_id": itc_scan_id,
            "issue_count": len(analysis.issues),
            "total_unclaimed_itc": str(analysis.total_unclaimed_itc),
        }
