"""Referral commission processing for CA firm white-label system."""

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.ca_firm import (
    CAClientRelationship,
    CAClientStatus,
    CAFirm,
    ReferralCommission,
    ReferralCommissionStatus,
)
from app.models.payment import Payment, PaymentStatus

logger = get_logger(__name__)


async def get_ca_firm_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> Optional[CAFirm]:
    result = await db.execute(
        select(CAFirm).where(CAFirm.owner_user_id == user_id, CAFirm.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def get_active_relationship(
    db: AsyncSession, organization_id: uuid.UUID
) -> Optional[CAClientRelationship]:
    """Return the active CA→client relationship for an organization, if any."""
    result = await db.execute(
        select(CAClientRelationship).where(
            CAClientRelationship.organization_id == organization_id,
            CAClientRelationship.status == CAClientStatus.active,
        )
    )
    return result.scalar_one_or_none()


def calculate_commission(amount_paise: int, rate: Decimal) -> Decimal:
    amount_rupees = Decimal(amount_paise) / Decimal(100)
    return (amount_rupees * rate).quantize(Decimal("0.01"))


async def process_payment_commission(
    db: AsyncSession, payment: Payment
) -> Optional[ReferralCommission]:
    """Create a ReferralCommission record for a completed subscription payment.

    Only fires for subscription payments (not one-time scans).
    Returns None if no active CA→client relationship exists.
    """
    from app.models.payment import PaymentType

    if payment.payment_type != PaymentType.subscription:
        return None
    if payment.status != PaymentStatus.paid:
        return None

    rel = await get_active_relationship(db, payment.organization_id)
    if rel is None:
        return None

    # Guard against duplicate commissions for the same payment
    existing = await db.execute(
        select(ReferralCommission).where(
            ReferralCommission.payment_id == payment.id
        )
    )
    if existing.scalar_one_or_none() is not None:
        logger.info("commission_already_exists", payment_id=str(payment.id))
        return None

    amount = calculate_commission(payment.amount_paise, rel.referral_commission_rate)

    commission = ReferralCommission(
        ca_firm_id=rel.ca_firm_id,
        organization_id=payment.organization_id,
        payment_id=payment.id,
        commission_amount=amount,
        commission_rate=rel.referral_commission_rate,
        status=ReferralCommissionStatus.pending,
    )
    db.add(commission)

    # Update the CA firm's running total
    result = await db.execute(
        select(CAFirm).where(CAFirm.id == rel.ca_firm_id)
    )
    ca_firm = result.scalar_one_or_none()
    if ca_firm is not None:
        ca_firm.total_referral_earnings = (
            Decimal(str(ca_firm.total_referral_earnings)) + amount
        )

    logger.info(
        "commission_created",
        ca_firm_id=str(rel.ca_firm_id),
        org_id=str(payment.organization_id),
        amount=str(amount),
    )
    return commission
