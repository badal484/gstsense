import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ITCScanStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ITCScan(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "itc_scans"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_month: Mapped[str] = mapped_column(String(7), nullable=False)
    gstr3b_s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    gstr2b_s3_key: Mapped[str] = mapped_column(String(500), nullable=False)

    total_invoices_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_unclaimed_itc: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    total_excess_claimed: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    total_at_risk: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )

    status: Mapped[ITCScanStatus] = mapped_column(
        Enum(ITCScanStatus, name="itc_scan_status"),
        nullable=False,
        default=ITCScanStatus.uploaded,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    organization = relationship("Organization", back_populates=None, lazy="selectin")
    issues: Mapped[list["ITCIssueRecord"]] = relationship(
        "ITCIssueRecord",
        back_populates="itc_scan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_itc_scans_org_month", "organization_id", "scan_month"),
    )


class ITCIssueRecord(Base, UUIDMixin):
    __tablename__ = "itc_issues"

    itc_scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itc_scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_gstin: Mapped[str] = mapped_column(String(15), nullable=False)
    supplier_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    available_itc: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    claimed_itc: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    difference: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    itc_scan: Mapped["ITCScan"] = relationship("ITCScan", back_populates="issues")

    __table_args__ = (
        Index("ix_itc_issues_scan_id", "itc_scan_id"),
        Index("ix_itc_issues_type", "issue_type"),
        Index("ix_itc_issues_scan_type", "itc_scan_id", "issue_type"),
    )
