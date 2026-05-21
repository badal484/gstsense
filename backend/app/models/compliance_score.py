import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class ComplianceScoreRecord(Base, UUIDMixin):
    __tablename__ = "compliance_scores"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    grade: Mapped[str] = mapped_column(String(3), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_compliance_scores_org_calculated", "organization_id", "calculated_at"),
    )

    def __repr__(self) -> str:
        return (
            f"ComplianceScoreRecord(org={self.organization_id!r}, "
            f"score={self.score!r}, grade={self.grade!r})"
        )
