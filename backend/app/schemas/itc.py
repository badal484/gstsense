import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.services.itc_analyzer import ITCIssueType


class ITCScanUploadResponse(BaseModel):
    scan_id: uuid.UUID
    status: str
    message: str = "ITC analysis started."


class ITCIssueResponse(BaseModel):
    supplier_gstin: str
    supplier_name: Optional[str]
    invoice_number: str
    invoice_date: Optional[str]
    issue_type: ITCIssueType
    available_itc: Decimal
    claimed_itc: Decimal
    difference: Decimal
    recommendation: str

    model_config = {"from_attributes": True}


class ITCAnalysisResponse(BaseModel):
    scan_id: uuid.UUID
    total_invoices_checked: int
    total_unique_suppliers: int
    total_unclaimed_itc: Decimal
    total_excess_claimed: Decimal
    total_at_risk: Decimal
    issues: list[ITCIssueResponse]
    issues_by_type: dict[str, int]

    model_config = {"from_attributes": True}


class ITCSummaryResponse(BaseModel):
    """Lightweight summary for dashboard widget — available on all plans."""
    total_unclaimed_itc: Decimal
    total_excess_claimed: Decimal
    total_at_risk: Decimal
    issue_count: int
    requires_upgrade: bool
