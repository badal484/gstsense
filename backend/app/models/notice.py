import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class NoticeType(str, enum.Enum):
    DRC_01 = "DRC_01"
    DRC_01A = "DRC_01A"
    DRC_01C = "DRC_01C"
    DRC_07 = "DRC_07"
    DRC_10 = "DRC_10"
    ASMT_10 = "ASMT_10"
    ASMT_11 = "ASMT_11"
    REG_03 = "REG_03"
    REG_17 = "REG_17"
    other = "other"


class DraftStatus(str, enum.Enum):
    pending = "pending"
    generated = "generated"
    reviewed = "reviewed"
    approved = "approved"
    failed = "failed"


class Notice(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "notices"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    notice_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    notice_type: Mapped[NoticeType] = mapped_column(
        Enum(NoticeType, name="notice_type"),
        default=NoticeType.other,
        nullable=False,
    )
    demand_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    # YYYY-MM format, e.g. "2024-03"
    tax_period: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    response_due_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    pdf_s3_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    draft_reply_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    draft_status: Mapped[DraftStatus] = mapped_column(
        Enum(DraftStatus, name="draft_status"),
        default=DraftStatus.pending,
        nullable=False,
        index=True,
    )
    # Set when a CA reviews and approves the AI-generated draft.
    reviewed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Required before the approved draft can be downloaded.
    icai_membership_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    # Warnings from citation validation step
    draft_warnings: Mapped[Optional[list[Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    # Secure share token (stored as SHA-256 hash)
    share_token: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    share_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ---- Relationships ----
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="notices",
        lazy="selectin",
    )
    reviewed_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reviewed_by_user_id],
        lazy="selectin",
    )

    # ---- Table-level indexes ----
    __table_args__ = (
        Index("ix_notices_org_draft_status", "organization_id", "draft_status"),
    )

    def __repr__(self) -> str:
        return (
            f"Notice(id={self.id!r}, notice_number={self.notice_number!r}, "
            f"notice_type={self.notice_type!r}, "
            f"draft_status={self.draft_status!r})"
        )
