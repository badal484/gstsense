import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from celery import Task
from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.mismatch import Mismatch
from app.models.scan import Scan, ScanStatus
from app.services.ai_explainer import explain_mismatches
from app.services.parser import parse_gstr1, parse_gstr3b
from app.services.reconciler import MismatchDetail, reconcile
from app.services.s3_service import s3_service
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


from typing import Any

def run_async(coro: Any) -> Any:
    """Run an async coroutine from a sync Celery task using a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="app.workers.scan_tasks.process_scan_task",
    max_retries=3,
    default_retry_delay=60,
    queue="normal",
)
def process_scan_task(self: Task, scan_id: str, org_id: str) -> Any:
    """Complete scan processing pipeline (sync shell → async core)."""
    logger.info("scan_task_started", scan_id=scan_id, task_id=self.request.id)
    try:
        return run_async(_process_scan_async(scan_id, org_id, self.request.id or ""))
    except Exception as exc:
        logger.error(
            "scan_task_failed_all_retries",
            scan_id=scan_id,
            error=str(exc),
        )
        run_async(_mark_scan_failed(scan_id, str(exc)))
        raise


async def _mark_scan_failed(scan_id: str, error_message: str) -> None:
    """Update scan status to failed in a dedicated session."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Scan)
            .where(Scan.id == uuid.UUID(scan_id))
            .values(
                status=ScanStatus.failed,
                error_message=error_message[:1000],
                completed_at=datetime.now(tz=timezone.utc),
            )
        )
        await db.commit()


async def _process_scan_async(
    scan_id: str,
    org_id: str,
    task_id: str,
) -> dict:
    """Async implementation of the full scan pipeline."""
    scan_uuid = uuid.UUID(scan_id)

    async with AsyncSessionLocal() as db:
        # ------------------------------------------------------------------
        # STEP 1: Transition to processing
        # ------------------------------------------------------------------
        await db.execute(
            update(Scan)
            .where(Scan.id == scan_uuid)
            .values(
                status=ScanStatus.processing,
                processing_started_at=datetime.now(tz=timezone.utc),
                celery_task_id=task_id,
            )
        )
        await db.commit()

        # Re-fetch to get S3 keys
        result = await db.execute(select(Scan).where(Scan.id == scan_uuid))
        scan = result.scalar_one()

        # ------------------------------------------------------------------
        # STEP 2 & 3: Download files from S3
        # ------------------------------------------------------------------
        logger.info("downloading_gstr1", scan_id=scan_id)
        try:
            gstr1_bytes = await s3_service.download_file(scan.gstr1_s3_key)
            gstr3b_bytes = await s3_service.download_file(scan.gstr3b_s3_key)
        except Exception as exc:
            logger.error("s3_download_error", scan_id=scan_id, error=str(exc))
            raise  # triggers Celery retry

        # ------------------------------------------------------------------
        # STEP 4 & 5: Parse files (validation errors → no retry)
        # ------------------------------------------------------------------
        from app.core.exceptions import ValidationError as GSTValidationError

        try:
            gstr1_result = parse_gstr1(gstr1_bytes)
        except GSTValidationError as exc:
            await _mark_scan_failed(scan_id, exc.message)
            return {"status": "failed", "reason": exc.message}

        try:
            gstr3b_result = parse_gstr3b(gstr3b_bytes)
        except GSTValidationError as exc:
            await _mark_scan_failed(scan_id, exc.message)
            return {"status": "failed", "reason": exc.message}

        all_warnings = gstr1_result.warnings + gstr3b_result.warnings

        # ------------------------------------------------------------------
        # STEP 6: Reconcile
        # ------------------------------------------------------------------
        recon = reconcile(
            gstr1_result.dataframe,
            gstr3b_result.dataframe,
            warnings=all_warnings,
        )
        logger.info(
            "reconciliation_complete",
            scan_id=scan_id,
            total_mismatches=recon.total_mismatches,
            total_rupee_risk=str(recon.total_rupee_risk),
        )

        # ------------------------------------------------------------------
        # STEP 7: Persist results
        # ------------------------------------------------------------------
        await db.execute(
            update(Scan)
            .where(Scan.id == scan_uuid)
            .values(
                total_invoices_scanned=recon.total_invoices_scanned,
                total_mismatches=recon.total_mismatches,
                total_rupee_risk=recon.total_rupee_risk,
            )
        )

        mismatch_models: list[Mismatch] = []
        for m in recon.mismatches:
            mismatch = Mismatch(
                scan_id=scan_uuid,
                invoice_number=m.invoice_number,
                supplier_gstin=m.supplier_gstin,
                mismatch_type=m.mismatch_type,
                gstr1_taxable_value=m.gstr1_taxable_value,
                gstr3b_taxable_value=m.gstr3b_taxable_value,
                gstr1_tax_amount=m.gstr1_tax_amount,
                gstr3b_tax_amount=m.gstr3b_tax_amount,
                rupee_difference=m.rupee_difference,
            )
            db.add(mismatch)
        await db.flush()
        await db.commit()

        # Re-query mismatches to get their DB-assigned IDs for the AI step
        mismatch_rows = await db.execute(
            select(Mismatch).where(Mismatch.scan_id == scan_uuid)
        )
        saved_mismatches = mismatch_rows.scalars().all()

        # ------------------------------------------------------------------
        # STEP 8: AI explanations (failure here must not block completion)
        # ------------------------------------------------------------------
        detail_list: list[MismatchDetail] = [
            MismatchDetail(
                invoice_number=m.invoice_number,
                supplier_gstin=m.supplier_gstin,
                mismatch_type=m.mismatch_type,
                gstr1_taxable_value=m.gstr1_taxable_value,
                gstr3b_taxable_value=m.gstr3b_taxable_value,
                gstr1_tax_amount=m.gstr1_tax_amount,
                gstr3b_tax_amount=m.gstr3b_tax_amount,
                rupee_difference=m.rupee_difference,
            )
            for m in saved_mismatches
        ]

        explained: list[MismatchDetail] = detail_list
        try:
            explained = await explain_mismatches(detail_list, scan.scan_month)
        except Exception as exc:
            logger.warning("ai_explain_failed_non_fatal", scan_id=scan_id, error=str(exc))

        # ------------------------------------------------------------------
        # STEP 9: Update mismatches with AI explanations
        # ------------------------------------------------------------------
        explanation_map: dict[str, str] = {
            m.invoice_number: m.ai_explanation
            for m in explained
            if m.ai_explanation
        }
        for saved in saved_mismatches:
            explanation = explanation_map.get(saved.invoice_number)
            if explanation:
                saved.ai_explanation = explanation
        await db.commit()

        # ------------------------------------------------------------------
        # STEP 10: Mark scan completed
        # ------------------------------------------------------------------
        now = datetime.now(tz=timezone.utc)
        await db.execute(
            update(Scan)
            .where(Scan.id == scan_uuid)
            .values(
                status=ScanStatus.completed,
                completed_at=now,
            )
        )

        # ------------------------------------------------------------------
        # STEP 11: Audit log
        # ------------------------------------------------------------------
        db.add(
            AuditLog(
                action="scan_completed",
                organization_id=uuid.UUID(org_id),
                resource_type="scan",
                resource_id=scan_uuid,
                metadata_json={
                    "total_mismatches": recon.total_mismatches,
                    "total_rupee_risk": str(recon.total_rupee_risk),
                    "processing_time_ms": recon.processing_time_ms,
                },
            )
        )
        await db.commit()

        logger.info(
            "scan_task_completed",
            scan_id=scan_id,
            total_mismatches=recon.total_mismatches,
            rupee_risk=str(recon.total_rupee_risk),
        )

        return {
            "status": "completed",
            "scan_id": scan_id,
            "total_mismatches": recon.total_mismatches,
            "total_rupee_risk": str(recon.total_rupee_risk),
        }
