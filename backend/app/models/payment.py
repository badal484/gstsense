import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Enum, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.scan import Scan


class PaymentType(str, enum.Enum):
    one_time_scan = "one_time_scan"
    subscription = "subscription"


class PaymentStatus(str, enum.Enum):
    created = "created"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"


class Payment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "payments"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    # Only set for one_time_scan payments; null for subscription payments.
    scan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("scans.id", ondelete="SET NULL"),
        nullable=True,
    )
    razorpay_order_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    # Set after Razorpay confirms the payment.
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
    )
    # Amount in paise — ₹499 = 49900.
    amount_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="INR",
        nullable=False,
    )
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="payment_type"),
        nullable=False,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.created,
        nullable=False,
        index=True,
    )
    # DB column name is "metadata". The Python attribute is "metadata_json"
    # to avoid shadowing SQLAlchemy's MetaData attribute on DeclarativeBase.
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        name="metadata",
        nullable=True,
    )

    # ---- Relationships ----
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="payments",
        lazy="selectin",
    )
    scan: Mapped[Optional["Scan"]] = relationship(
        "Scan",
        back_populates="payment",
        lazy="selectin",
    )

    # ---- Table-level indexes ----
    __table_args__ = (
        Index("ix_payments_org_status", "organization_id", "status"),
    )

    # ---- Properties ----
    @property
    def amount_rupees(self) -> Decimal:
        return Decimal(self.amount_paise) / Decimal(100)

    def __repr__(self) -> str:
        return (
            f"Payment(id={self.id!r}, "
            f"razorpay_order_id={self.razorpay_order_id!r}, "
            f"status={self.status!r}, amount_rupees={self.amount_rupees!r})"
        )
