import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.scan import Scan


class MismatchType(str, enum.Enum):
    missing_in_3b = "missing_in_3b"
    missing_in_1 = "missing_in_1"
    value_mismatch = "value_mismatch"
    tax_mismatch = "tax_mismatch"


class Mismatch(Base, UUIDMixin):
    """Mismatches are append-only — never updated after creation.

    Inherits only UUIDMixin (id). TimestampMixin is deliberately excluded
    so no ``updated_at`` column is created on this table.
    """

    __tablename__ = "mismatches"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    invoice_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    supplier_gstin: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
    )
    supplier_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    mismatch_type: Mapped[MismatchType] = mapped_column(
        Enum(MismatchType, name="mismatch_type"),
        nullable=False,
        index=True,
    )
    gstr1_taxable_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0"),
        nullable=False,
    )
    gstr3b_taxable_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0"),
        nullable=False,
    )
    gstr1_tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0"),
        nullable=False,
    )
    gstr3b_tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0"),
        nullable=False,
    )
    # Always stored as the absolute value of (gstr1 − gstr3b).
    rupee_difference: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    # Set asynchronously after the AI explanation worker completes.
    ai_explanation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # ---- Relationships ----
    scan: Mapped["Scan"] = relationship(
        "Scan",
        back_populates="mismatches",
        lazy="selectin",
    )

    # ---- Table-level indexes ----
    __table_args__ = (
        Index("ix_mismatches_scan_type", "scan_id", "mismatch_type"),
    )

    def __repr__(self) -> str:
        return (
            f"Mismatch(id={self.id!r}, invoice_number={self.invoice_number!r}, "
            f"mismatch_type={self.mismatch_type!r}, "
            f"rupee_difference={self.rupee_difference!r})"
        )
