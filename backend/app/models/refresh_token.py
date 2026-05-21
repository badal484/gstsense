import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class RefreshToken(Base, UUIDMixin):
    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_refresh_tokens_jti_revoked", "jti", "revoked_at"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"RefreshToken(jti={self.jti!r}, user_id={self.user_id!r}, revoked={self.revoked_at is not None!r})"
