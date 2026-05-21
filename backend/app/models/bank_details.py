import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.ca_firm import CAFirm


class CABankDetails(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ca_bank_details"

    ca_firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ca_firms.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    account_holder_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    ifsc_code: Mapped[str] = mapped_column(String(11), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    upi_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    ca_firm: Mapped["CAFirm"] = relationship("CAFirm", lazy="selectin", foreign_keys=[ca_firm_id])

    def __repr__(self) -> str:
        return f"CABankDetails(ca_firm_id={self.ca_firm_id!r}, bank={self.bank_name!r})"
