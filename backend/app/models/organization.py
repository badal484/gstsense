import enum
import uuid
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.notice import Notice
    from app.models.payment import Payment
    from app.models.scan import Scan
    from app.models.subscription import Subscription
    from app.models.user import User


class Plan(str, enum.Enum):
    free = "free"
    smb = "smb"
    growth = "growth"
    ca_firm = "ca_firm"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"
    past_due = "past_due"
    trialing = "trialing"
    inactive = "inactive"


class Organization(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organizations"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    business_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    gstin: Mapped[str] = mapped_column(
        String(15),
        unique=True,
        index=True,
        nullable=False,
    )
    # Derived from the first 2 characters of the GSTIN (state code).
    state_code: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
    )
    plan: Mapped[Plan] = mapped_column(
        Enum(Plan, name="org_plan"),
        default=Plan.free,
        nullable=False,
        index=True,
    )
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="org_subscription_status"),
        default=SubscriptionStatus.inactive,
        nullable=False,
        index=True,
    )
    invoice_limit: Mapped[int] = mapped_column(
        Integer,
        default=500,
        nullable=False,
    )
    invoices_used_this_month: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    billing_cycle_start: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    billing_cycle_end: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    razorpay_customer_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # ---- Relationships ----
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="organizations",
        lazy="selectin",
    )
    scans: Mapped[list["Scan"]] = relationship(
        "Scan",
        back_populates="organization",
        lazy="selectin",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="organization",
        lazy="selectin",
    )
    subscription: Mapped[Optional["Subscription"]] = relationship(
        "Subscription",
        back_populates="organization",
        uselist=False,
        lazy="selectin",
    )
    notices: Mapped[list["Notice"]] = relationship(
        "Notice",
        back_populates="organization",
        lazy="selectin",
    )

    # ---- Table-level indexes ----
    __table_args__ = (
        Index("ix_organizations_plan_sub_status", "plan", "subscription_status"),
    )

    # ---- Properties ----
    @property
    def has_active_subscription(self) -> bool:
        return self.subscription_status == SubscriptionStatus.active

    @property
    def is_invoice_limit_reached(self) -> bool:
        return self.invoices_used_this_month >= self.invoice_limit

    def __repr__(self) -> str:
        return (
            f"Organization(id={self.id!r}, gstin={self.gstin!r}, "
            f"plan={self.plan!r})"
        )
