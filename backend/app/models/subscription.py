import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class SubscriptionPlan(str, enum.Enum):
    smb = "smb"
    growth = "growth"
    ca_firm = "ca_firm"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"
    past_due = "past_due"
    paused = "paused"


class Subscription(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    # unique=True enforces the one-subscription-per-org constraint at DB level.
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(SubscriptionPlan, name="subscription_plan"),
        nullable=False,
    )
    razorpay_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status"),
        default=SubscriptionStatus.active,
        nullable=False,
        index=True,
    )
    current_period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    current_period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # ---- Relationships ----
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="subscription",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"Subscription(id={self.id!r}, plan={self.plan!r}, "
            f"status={self.status!r})"
        )
