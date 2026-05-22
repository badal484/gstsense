import asyncio
import functools
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from celery import Task
from sqlalchemy import select, update

from app.core.database import celery_db_session
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
    """Update scan status to failed, clean up S3 files, and notify the user."""
    async with celery_db_session() as db:
        result = await db.execute(select(Scan).where(Scan.id == uuid.UUID(scan_id)))
        scan = result.scalar_one_or_none()

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

    # S3 cleanup — best-effort, non-blocking
    if scan:
        for key in [scan.gstr1_s3_key, scan.gstr3b_s3_key]:
            if key:
                try:
                    await s3_service.delete_file(key)
                except Exception as exc:
                    logger.warning("s3_cleanup_failed", key=key, error=str(exc))

        # Notify user — fetch org owner details
        try:
            await _notify_scan_failed(scan)
        except Exception as exc:
            logger.warning("scan_failure_notify_failed", scan_id=scan_id, error=str(exc))


async def _notify_scan_failed(scan: Scan) -> None:
    """Send WhatsApp + email notifications on scan failure (non-fatal)."""
    from app.models.organization import Organization
    from app.models.user import User
    from app.services.email_service import email_service
    from app.services.whatsapp_service import whatsapp_service

    async with celery_db_session() as db:
        org_result = await db.execute(
            select(Organization).where(Organization.id == scan.organization_id)
        )
        org = org_result.scalar_one_or_none()
        if org is None:
            return

        user_result = await db.execute(
            select(User).where(User.id == org.owner_user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            return

    subject = "Your GSTSense scan could not be completed"
    body = f"""
    <h2>Scan Processing Failed</h2>
    <p>Hi {user.full_name},</p>
    <p>Unfortunately, we were unable to process the scan for <strong>{org.business_name}</strong>
    ({scan.scan_month}).</p>
    <p>Please check that your GSTR-1 and GSTR-3B files are valid and try again.
    If the problem persists, contact support.</p>
    <a href="https://gstsense.in/scan" style="background:#1d4ed8;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;">Try Again</a>
    """
    try:
        from app.services.email_service import _wrap
        await email_service._send(user.email, subject, _wrap(body))
    except Exception as exc:
        logger.warning("scan_fail_email_failed", error=str(exc))

    if user.phone:
        try:
            await whatsapp_service.send_scan_complete_notification(
                phone=user.phone,
                business_name=org.business_name,
                scan_month=scan.scan_month,
                total_mismatches=0,
                total_rupee_risk=Decimal("0"),
                scan_id=str(scan.id),
            )
        except Exception as exc:
            logger.warning("scan_fail_whatsapp_failed", error=str(exc))


async def _process_scan_async(
    scan_id: str,
    org_id: str,
    task_id: str,
) -> dict:
    """Async implementation of the full scan pipeline."""
    scan_uuid = uuid.UUID(scan_id)

    async with celery_db_session() as db:
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
        # Run in thread pool so the event loop stays responsive to status polls.
        # ------------------------------------------------------------------
        from app.core.exceptions import ValidationError as GSTValidationError

        try:
            gstr1_result = await asyncio.to_thread(parse_gstr1, gstr1_bytes)
        except GSTValidationError as exc:
            await _mark_scan_failed(scan_id, exc.message)
            return {"status": "failed", "reason": exc.message}

        try:
            gstr3b_result = await asyncio.to_thread(parse_gstr3b, gstr3b_bytes)
        except GSTValidationError as exc:
            await _mark_scan_failed(scan_id, exc.message)
            return {"status": "failed", "reason": exc.message}

        all_warnings = gstr1_result.warnings + gstr3b_result.warnings

        # ------------------------------------------------------------------
        # STEP 6: Reconcile (CPU-bound — thread pool)
        # ------------------------------------------------------------------
        recon = await asyncio.to_thread(
            functools.partial(
                reconcile,
                gstr1_result.dataframe,
                gstr3b_result.dataframe,
                warnings=all_warnings,
            )
        )
        logger.info(
            "reconciliation_complete",
            scan_id=scan_id,
            total_mismatches=recon.total_mismatches,
            total_rupee_risk=str(recon.total_rupee_risk),
        )

        # ------------------------------------------------------------------
        # STEP 7: Persist results + update invoice usage
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

        # Increment invoice usage by actual count (not 1 at upload time)
        from app.models.organization import Organization
        org_result = await db.execute(
            select(Organization).where(Organization.id == uuid.UUID(org_id))
        )
        org_obj = org_result.scalar_one_or_none()
        if org_obj is not None:
            new_usage = org_obj.invoices_used_this_month + recon.total_invoices_scanned
            if new_usage > org_obj.invoice_limit:
                await _mark_scan_failed(
                    scan_id,
                    "Invoice limit reached for this month. Upgrade your plan to scan more invoices.",
                )
                return {"status": "failed", "reason": "invoice_limit_reached"}
            org_obj.invoices_used_this_month = new_usage

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
        # STEP 10: Generate PDF report and upload to S3
        # ------------------------------------------------------------------
        pdf_s3_key: Optional[str] = None
        try:
            from app.services.pdf_generator import ReportData, generate_mismatch_report
            pdf_mismatches = [
                {
                    "invoice_number": m.invoice_number,
                    "supplier_gstin": m.supplier_gstin,
                    "mismatch_type": m.mismatch_type.value if hasattr(m.mismatch_type, "value") else m.mismatch_type,
                    "gstr1_taxable_value": m.gstr1_taxable_value,
                    "gstr3b_taxable_value": m.gstr3b_taxable_value,
                    "gstr1_tax_amount": m.gstr1_tax_amount,
                    "gstr3b_tax_amount": m.gstr3b_tax_amount,
                    "rupee_difference": m.rupee_difference,
                    "ai_explanation": getattr(m, "ai_explanation", None),
                }
                for m in saved_mismatches
            ]
            report_data = ReportData(
                organization_name=org_obj.business_name if org_obj else "",
                gstin=org_obj.gstin if org_obj else "",
                scan_month=scan.scan_month,
                total_invoices_scanned=recon.total_invoices_scanned,
                total_mismatches=recon.total_mismatches,
                total_rupee_risk=recon.total_rupee_risk,
                mismatches=pdf_mismatches,
                generated_at=datetime.now(tz=timezone.utc),
            )
            pdf_bytes = await asyncio.to_thread(generate_mismatch_report, report_data)
            pdf_key = s3_service.build_scan_pdf_key(org_id, scan_id)
            await s3_service.upload_file(
                pdf_bytes, pdf_key, content_type="application/pdf"
            )
            pdf_s3_key = pdf_key
            logger.info("scan_pdf_generated", scan_id=scan_id, s3_key=pdf_key)
        except Exception as exc:
            logger.warning("scan_pdf_generation_failed", scan_id=scan_id, error=str(exc))

        # ------------------------------------------------------------------
        # STEP 11: Mark scan completed
        # ------------------------------------------------------------------
        now = datetime.now(tz=timezone.utc)
        update_values: dict = dict(status=ScanStatus.completed, completed_at=now)
        if pdf_s3_key:
            update_values["pdf_s3_key"] = pdf_s3_key
        await db.execute(
            update(Scan)
            .where(Scan.id == scan_uuid)
            .values(**update_values)
        )

        # ------------------------------------------------------------------
        # STEP 12: Audit log
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
