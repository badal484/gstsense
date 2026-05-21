import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.mismatch import Mismatch
    from app.models.organization import Organization
    from app.models.payment import Payment


class ScanStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Scan(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "scans"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # YYYY-MM format, e.g. "2024-03"
    scan_month: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
    )
    gstr1_s3_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    gstr3b_s3_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    # Populated after the PDF report is generated.
    pdf_s3_key: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    total_invoices_scanned: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_mismatches: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_rupee_risk: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0"),
        nullable=False,
    )
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status"),
        default=ScanStatus.uploaded,
        nullable=False,
        index=True,
    )
    is_paid: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        index=True,
    )
    # Populated when status transitions to "failed".
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Celery task ID stored so the task can be revoked or inspected.
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # ---- Relationships ----
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="scans",
        lazy="selectin",
    )
    mismatches: Mapped[list["Mismatch"]] = relationship(
        "Mismatch",
        back_populates="scan",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    payment: Mapped[Optional["Payment"]] = relationship(
        "Payment",
        back_populates="scan",
        uselist=False,
        lazy="selectin",
    )

    # ---- Table-level indexes ----
    __table_args__ = (
        Index("ix_scans_org_month", "organization_id", "scan_month"),
        Index("ix_scans_org_status", "organization_id", "status"),
    )

    # ---- Properties ----
    @property
    def processing_duration_seconds(self) -> Optional[float]:
        """Wall-clock seconds from processing start to completion.

        Returns ``None`` if the scan has not completed yet.
        """
        if self.processing_started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.processing_started_at).total_seconds()

    def __repr__(self) -> str:
        return (
            f"Scan(id={self.id!r}, scan_month={self.scan_month!r}, "
            f"status={self.status!r})"
        )
