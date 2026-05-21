import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """Immutable compliance log — append-only, never updated or deleted.

    Required under the DPDP Act to maintain a tamper-evident record of all
    data access and mutations. No ``updated_at`` column exists — intentionally.

    Foreign-key constraints are deliberately absent so that audit entries
    survive the deletion of the referenced user or organisation.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # No FK — intentional: user may be deleted but log must be preserved.
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
        index=True,
    )
    # No FK — intentional: org may be deleted but log must be preserved.
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
        index=True,
    )

    # Action strings: user_registered, user_logged_in, user_login_failed,
    # scan_uploaded, scan_completed, report_viewed, report_downloaded,
    # payment_created, payment_completed, notice_uploaded,
    # notice_draft_generated, notice_draft_approved
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    # Examples: scan, payment, notice, user
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
    )
    # Supports both IPv4 (max 15 chars) and IPv6 (max 45 chars).
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    # DB column name is "metadata". Python attribute avoids shadowing
    # SQLAlchemy's internal MetaData attribute on DeclarativeBase.
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        name="metadata",
        nullable=True,
    )

    # ---- Table-level indexes ----
    __table_args__ = (
        Index("ix_audit_logs_org_created_at", "organization_id", "created_at"),
        Index("ix_audit_logs_user_created_at", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"AuditLog(id={self.id!r}, action={self.action!r}, "
            f"user_id={self.user_id!r})"
        )
