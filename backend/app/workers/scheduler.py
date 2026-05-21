"""Celery Beat scheduler — periodic tasks for GSTSense."""

import asyncio
import calendar
from datetime import date, datetime, timezone

from celery.schedules import crontab

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

# -----------------------------------------------------------------------
# Beat schedule
# -----------------------------------------------------------------------

celery_app.conf.beat_schedule = {
    "send-gstr1-reminders": {
        "task": "app.workers.scheduler.send_filing_reminders",
        "schedule": crontab(hour=9, minute=0),
        "args": ["GSTR1"],
        "options": {"queue": "low"},
    },
    "send-gstr3b-reminders": {
        "task": "app.workers.scheduler.send_filing_reminders",
        "schedule": crontab(hour=9, minute=30),
        "args": ["GSTR3B"],
        "options": {"queue": "low"},
    },
    "reset-monthly-invoice-counts": {
        "task": "app.workers.scheduler.reset_invoice_counts",
        "schedule": crontab(hour=0, minute=0, day_of_month=1),
        "options": {"queue": "low"},
    },
    "calculate-compliance-scores": {
        "task": "app.workers.scheduler.update_compliance_scores",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "low"},
    },
    "process-commission-payouts": {
        "task": "app.workers.scheduler.process_monthly_payouts",
        "schedule": crontab(hour=10, minute=0, day_of_month=5),
        "options": {"queue": "low"},
    },
}


def run_async(coro) -> dict:  # type: ignore[no-untyped-def]
    loop = asyncio.new_event_loop()
    try:
        result: dict = loop.run_until_complete(coro)
        return result
    finally:
        loop.close()


# -----------------------------------------------------------------------
# Tasks
# -----------------------------------------------------------------------


@celery_app.task(
    name="app.workers.scheduler.send_filing_reminders",
    queue="low",
)
def send_filing_reminders(filing_type: str) -> dict:
    """Send WhatsApp reminders for upcoming GST filing deadlines."""
    return run_async(_send_filing_reminders_async(filing_type))


async def _send_filing_reminders_async(filing_type: str) -> dict:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy import NullPool, select
    from app.core.config import settings
    from app.models.organization import Organization, SubscriptionStatus
    from app.models.user import User
    from app.services.whatsapp_service import whatsapp_service

    DEADLINE_DAYS = {"GSTR1": 11, "GSTR3B": 20}
    REMINDER_DAYS = {7, 3, 1}

    today = date.today()
    day_of_month = DEADLINE_DAYS.get(filing_type)
    if day_of_month is None:
        logger.error("unknown_filing_type", filing_type=filing_type)
        return {"sent": 0, "failed": 0, "skipped": 0}

    # Calculate next deadline
    if today.day <= day_of_month:
        deadline = today.replace(day=day_of_month)
    else:
        if today.month == 12:
            deadline = date(today.year + 1, 1, day_of_month)
        else:
            last_day = calendar.monthrange(today.year, today.month + 1)[1]
            deadline = date(today.year, today.month + 1, min(day_of_month, last_day))

    days_until = (deadline - today).days

    if days_until not in REMINDER_DAYS:
        logger.info(
            "reminder_skipped_not_reminder_day",
            filing_type=filing_type,
            days_until=days_until,
        )
        return {"sent": 0, "failed": 0, "skipped": 1}

    due_date_str = deadline.strftime("%-d %B %Y")
    sent = failed = skipped = 0

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as db:
            orgs_q = await db.execute(
                select(Organization).where(
                    Organization.subscription_status.in_([
                        SubscriptionStatus.active,
                        SubscriptionStatus.trialing,
                    ])
                )
            )
            orgs = orgs_q.scalars().all()

            from app.models.user_preferences import UserPreferences
            for org in orgs:
                user_q = await db.execute(
                    select(User).where(User.id == org.owner_user_id)
                )
                user = user_q.scalar_one_or_none()
                if user is None or not user.phone:
                    continue

                # Respect notification preferences (default True if no record)
                prefs_q = await db.execute(
                    select(UserPreferences).where(UserPreferences.user_id == user.id)
                )
                prefs = prefs_q.scalar_one_or_none()
                if prefs is not None and not prefs.whatsapp_deadline_reminders:
                    skipped += 1
                    continue

                try:
                    success = await whatsapp_service.send_deadline_reminder(
                        phone=user.phone,
                        business_name=org.business_name,
                        filing_type=filing_type,
                        due_date=due_date_str,
                        days_remaining=days_until,
                    )
                    if success:
                        sent += 1
                        logger.info(
                            "reminder_sent",
                            filing_type=filing_type,
                            org_id=str(org.id),
                            days_until=days_until,
                        )
                    else:
                        failed += 1
                except Exception as exc:
                    failed += 1
                    logger.error(
                        "reminder_error",
                        org_id=str(org.id),
                        error=str(exc),
                    )
    finally:
        await engine.dispose()

    logger.info(
        "filing_reminders_complete",
        filing_type=filing_type,
        sent=sent,
        failed=failed,
    )
    return {"sent": sent, "failed": failed, "skipped": 0}


@celery_app.task(
    name="app.workers.scheduler.reset_invoice_counts",
    queue="low",
)
def reset_invoice_counts() -> dict:
    """Reset invoices_used_this_month to 0 for all organisations."""
    return run_async(_reset_invoice_counts_async())


async def _reset_invoice_counts_async() -> dict:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy import NullPool, update
    from app.core.config import settings
    from app.models.organization import Organization

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as db:
            result = await db.execute(
                update(Organization).values(invoices_used_this_month=0)
            )
            await db.commit()
            count = result.rowcount
    finally:
        await engine.dispose()

    logger.info("monthly_invoice_counts_reset", count=count)
    return {"reset": count}


@celery_app.task(
    name="app.workers.scheduler.update_compliance_scores",
    queue="low",
)
def update_compliance_scores() -> dict:
    """Recalculate compliance scores for all active organisations."""
    return run_async(_update_compliance_scores_async())


async def _update_compliance_scores_async() -> dict:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy import NullPool, delete, select
    from app.core.config import settings
    from app.models.compliance_score import ComplianceScoreRecord
    from app.models.organization import Organization, SubscriptionStatus
    from app.services.compliance_score import calculate_org_compliance_score
    from datetime import timedelta

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    updated = 0
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(days=90)

    try:
        async with async_session() as db:
            orgs_q = await db.execute(
                select(Organization).where(
                    Organization.subscription_status.in_([
                        SubscriptionStatus.active,
                        SubscriptionStatus.trialing,
                    ])
                )
            )
            orgs = orgs_q.scalars().all()

            for org in orgs:
                try:
                    score_result = await calculate_org_compliance_score(str(org.id), db)
                    record = ComplianceScoreRecord(
                        organization_id=org.id,
                        score=score_result.score,
                        grade=score_result.grade,
                    )
                    db.add(record)
                    updated += 1
                except Exception as exc:
                    logger.error("compliance_score_update_error", org_id=str(org.id), error=str(exc))

            # Delete scores older than 90 days
            await db.execute(
                delete(ComplianceScoreRecord).where(
                    ComplianceScoreRecord.calculated_at < cutoff
                )
            )
            await db.commit()
    finally:
        await engine.dispose()

    logger.info("compliance_scores_updated", count=updated)
    return {"updated": updated}


@celery_app.task(
    name="app.workers.scheduler.process_monthly_payouts",
    queue="low",
)
def process_monthly_payouts() -> dict:
    """Process commission payouts on 5th of each month."""
    return run_async(_process_monthly_payouts_async())


async def _process_monthly_payouts_async() -> dict:
    from decimal import Decimal
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy import NullPool, select
    from app.core.config import settings
    from app.models.ca_firm import CAFirm, ReferralCommission, ReferralCommissionStatus

    MINIMUM_PAYOUT = Decimal("100.00")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    processed = skipped = 0
    now = datetime.now(tz=timezone.utc)

    try:
        async with async_session() as db:
            firms_q = await db.execute(
                select(CAFirm).where(CAFirm.is_active.is_(True))
            )
            firms = firms_q.scalars().all()

            for firm in firms:
                pending_q = await db.execute(
                    select(ReferralCommission).where(
                        ReferralCommission.ca_firm_id == firm.id,
                        ReferralCommission.status == ReferralCommissionStatus.pending,
                    )
                )
                pending = pending_q.scalars().all()
                if not pending:
                    continue

                total = sum(c.commission_amount for c in pending)
                if total < MINIMUM_PAYOUT:
                    skipped += 1
                    continue

                for commission in pending:
                    commission.status = ReferralCommissionStatus.paid
                    commission.payout_date = now

                processed += 1
                logger.info(
                    "commission_payout_processed",
                    ca_firm_id=str(firm.id),
                    total=str(total),
                    commissions=len(pending),
                )

            await db.commit()
    finally:
        await engine.dispose()

    logger.info("monthly_payouts_complete", processed=processed, skipped=skipped)
    return {"processed": processed, "skipped": skipped}
