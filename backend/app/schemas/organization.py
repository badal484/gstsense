import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class OrganizationDetailResponse(BaseModel):
    id: uuid.UUID
    business_name: str
    gstin: str
    state_code: str
    plan: str
    subscription_status: str
    invoice_limit: int
    invoices_used_this_month: int
    has_active_subscription: bool
    is_invoice_limit_reached: bool
    billing_cycle_start: Optional[date]
    billing_cycle_end: Optional[date]

    model_config = {"from_attributes": True}


class UsageStatsResponse(BaseModel):
    total_scans: int
    total_mismatches_found: int
    total_rupee_risk_found: Decimal
    total_itc_recovered: Decimal
    scans_this_month: int
    invoices_used_this_month: int
    invoice_limit: int
