"""Background task for bulk CA report PDF generation."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.database import celery_db_session
from app.core.logging import get_logger
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
    name="app.workers.report_tasks.generate_bulk_ca_report_task",
    max_retries=2,
    default_retry_delay=30,
    queue="low",
)
def generate_bulk_ca_report_task(self: Any, ca_firm_id: str, org_id: str) -> Any:
    logger.info("bulk_report_task_started", ca_firm_id=ca_firm_id, task_id=self.request.id)
    try:
        return run_async(_generate_bulk_report_async(ca_firm_id, org_id))
    except Exception as exc:
        logger.error("bulk_report_task_failed", ca_firm_id=ca_firm_id, error=str(exc))
        raise self.retry(exc=exc)


async def _generate_bulk_report_async(ca_firm_id: str, org_id: str) -> dict:
    from sqlalchemy import select

    from app.models.ca_firm import CAFirm, CAClientRelationship, CAClientStatus
    from app.models.referral import ReferralCommission
    from app.services.pdf_generator import generate_bulk_ca_report
    from app.services.s3_service import s3_service

    async with celery_db_session() as db:
        firm_q = await db.execute(select(CAFirm).where(CAFirm.id == uuid.UUID(ca_firm_id)))
        ca_firm = firm_q.scalar_one_or_none()
        if ca_firm is None:
            raise ValueError(f"CA firm {ca_firm_id} not found")

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

    s3_key = f"reports/ca/{org_id}/bulk_report_{datetime.now(tz=timezone.utc).strftime('%Y%m%d%H%M%S')}.pdf"
    await s3_service.upload_file(pdf_bytes, s3_key, content_type="application/pdf")

    download_url = await s3_service.generate_presigned_url(
        s3_key, expiry_seconds=3600
    )

    logger.info("bulk_report_task_completed", ca_firm_id=ca_firm_id, s3_key=s3_key)
    return {"status": "completed", "download_url": download_url}
