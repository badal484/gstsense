import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

ICAI_NUMBER_PATTERN = re.compile(
    r"^[A-Z]{1,3}[0-9]{4,8}[A-Z]?$",
    re.IGNORECASE,
)


class NoticeUploadResponse(BaseModel):
    notice_id: uuid.UUID
    status: str
    notice_type: Optional[str] = None
    notice_number: Optional[str] = None
    demand_amount: Optional[Decimal] = None
    response_due_date: Optional[date] = None
    message: str = "Notice uploaded. Draft reply being generated."


class NoticeDetailResponse(BaseModel):
    id: uuid.UUID
    notice_number: str
    notice_type: str
    demand_amount: Optional[Decimal] = None
    tax_period: Optional[str] = None
    response_due_date: Optional[date] = None
    draft_status: str
    icai_membership_number: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NoticeDraftResponse(BaseModel):
    notice_id: uuid.UUID
    notice_number: str
    draft_reply_text: str
    draft_status: str
    disclaimer_text: str
    warnings: list[str] = []

    model_config = {"from_attributes": True}


class NoticeApprovalRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


class NoticeListResponse(BaseModel):
    notices: list[NoticeDetailResponse]
    total: int


class VerifyCredentialsRequest(BaseModel):
    icai_number: str

    @field_validator("icai_number")
    @classmethod
    def validate_icai(cls, v: str) -> str:
        normalized = v.strip().upper()
        if not ICAI_NUMBER_PATTERN.match(normalized):
            raise ValueError(
                "Invalid ICAI membership number format. "
                "Expected format: MRN123456 or FRN100001W"
            )
        return normalized
