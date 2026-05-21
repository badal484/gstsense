import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserPreferences(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    whatsapp_deadline_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    whatsapp_scan_complete: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    whatsapp_mismatch_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_scan_complete: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_weekly_digest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_product_updates: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship("User", lazy="selectin", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"UserPreferences(user_id={self.user_id!r})"
