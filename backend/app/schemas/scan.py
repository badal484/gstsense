import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, field_validator

from app.models.mismatch import MismatchType
from app.models.scan import ScanStatus


class ScanUploadResponse(BaseModel):
    scan_id: uuid.UUID
    status: ScanStatus
    message: str = "Scan started. You will be notified when complete."

    @field_validator("status", mode="before")
    @classmethod
    def enum_to_str(cls, v: Any) -> str:
        return str(v.value) if hasattr(v, "value") else str(v)


class ScanStatusResponse(BaseModel):
    scan_id: uuid.UUID
    status: ScanStatus
    created_at: datetime
    completed_at: Optional[datetime]
    processing_duration_seconds: Optional[float]

    model_config = {"from_attributes": True}

    @field_validator("status", mode="before")
    @classmethod
    def enum_to_str(cls, v: Any) -> str:
        return str(v.value) if hasattr(v, "value") else str(v)

    @field_validator("scan_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: Any) -> uuid.UUID:
        return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


class ScanPreviewResponse(BaseModel):
    scan_id: uuid.UUID
    total_mismatches: int
    total_rupee_risk: Decimal
    is_paid: bool
    scan_month: str

    model_config = {"from_attributes": True}

    @field_validator("scan_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: Any) -> uuid.UUID:
        return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


class MismatchResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    supplier_gstin: str
    supplier_name: Optional[str]
    mismatch_type: MismatchType
    gstr1_taxable_value: Decimal
    gstr3b_taxable_value: Decimal
    gstr1_tax_amount: Decimal
    gstr3b_tax_amount: Decimal
    rupee_difference: Decimal
    ai_explanation: Optional[str]

    model_config = {"from_attributes": True}

    @field_validator("mismatch_type", mode="before")
    @classmethod
    def enum_to_str(cls, v: Any) -> str:
        return str(v.value) if hasattr(v, "value") else str(v)

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: Any) -> uuid.UUID:
        return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


class ScanReportResponse(BaseModel):
    scan_id: uuid.UUID
    scan_month: str
    total_invoices_scanned: int
    total_mismatches: int
    total_rupee_risk: Decimal
    mismatches: list[MismatchResponse]

    model_config = {"from_attributes": True}

    @field_validator("scan_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: Any) -> uuid.UUID:
        return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


class ScanListItem(BaseModel):
    id: uuid.UUID
    scan_month: str
    status: ScanStatus
    total_invoices_scanned: int
    total_mismatches: int
    total_rupee_risk: Decimal
    is_paid: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("status", mode="before")
    @classmethod
    def enum_to_str(cls, v: Any) -> str:
        return str(v.value) if hasattr(v, "value") else str(v)

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: Any) -> uuid.UUID:
        return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


class ScanListResponse(BaseModel):
    scans: list[ScanListItem]
    total: int
    page: int
    limit: int
