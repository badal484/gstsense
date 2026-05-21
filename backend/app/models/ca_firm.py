import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.payment import Payment
    from app.models.user import User


class CAClientStatus(str, enum.Enum):
    active = "active"
    removed = "removed"


class ReferralCommissionStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    cancelled = "cancelled"


class CAFirm(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ca_firms"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
        nullable=False,
    )
    firm_name: Mapped[str] = mapped_column(String(255), nullable=False)
    icai_firm_registration_number: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    primary_ca_name: Mapped[str] = mapped_column(String(255), nullable=False)
    icai_membership_number: Mapped[str] = mapped_column(String(50), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    white_label_subdomain: Mapped[Optional[str]] = mapped_column(
        String(63), unique=True, index=True, nullable=True
    )
    logo_s3_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str] = mapped_column(
        String(7), default="#534AB7", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    total_clients: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_referral_earnings: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    # ---- Relationships ----
    owner: Mapped["User"] = relationship("User", lazy="selectin")
    client_relationships: Mapped[list["CAClientRelationship"]] = relationship(
        "CAClientRelationship",
        back_populates="ca_firm",
        lazy="selectin",
    )
    commissions: Mapped[list["ReferralCommission"]] = relationship(
        "ReferralCommission",
        back_populates="ca_firm",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"CAFirm(id={self.id!r}, firm_name={self.firm_name!r})"


class CAClientRelationship(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ca_client_relationships"

    ca_firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ca_firms.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[CAClientStatus] = mapped_column(
        Enum(CAClientStatus, name="ca_client_status"),
        default=CAClientStatus.active,
        nullable=False,
        index=True,
    )
    referral_commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0.1500"), nullable=False
    )

    # ---- Relationships ----
    ca_firm: Mapped["CAFirm"] = relationship(
        "CAFirm", back_populates="client_relationships", lazy="selectin"
    )
    organization: Mapped["Organization"] = relationship(
        "Organization", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("ca_firm_id", "organization_id", name="uq_ca_firm_org"),
    )

    def __repr__(self) -> str:
        return (
            f"CAClientRelationship(ca_firm_id={self.ca_firm_id!r}, "
            f"org_id={self.organization_id!r}, status={self.status!r})"
        )


class ReferralCommission(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "referral_commissions"

    ca_firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ca_firms.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    commission_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False
    )
    status: Mapped[ReferralCommissionStatus] = mapped_column(
        Enum(ReferralCommissionStatus, name="referral_commission_status"),
        default=ReferralCommissionStatus.pending,
        nullable=False,
        index=True,
    )
    payout_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Relationships ----
    ca_firm: Mapped["CAFirm"] = relationship(
        "CAFirm", back_populates="commissions", lazy="selectin"
    )
    organization: Mapped["Organization"] = relationship(
        "Organization", lazy="selectin"
    )
    payment: Mapped["Payment"] = relationship("Payment", lazy="selectin")

    __table_args__ = (
        Index("ix_referral_commissions_firm_status", "ca_firm_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"ReferralCommission(id={self.id!r}, ca_firm_id={self.ca_firm_id!r}, "
            f"amount={self.commission_amount!r}, status={self.status!r})"
        )
