import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_ICAI_FIRM_PATTERN = re.compile(r"^[A-Z0-9]{3,20}$")
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
_SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$")


class CAFirmCreate(BaseModel):
    firm_name: str = Field(..., min_length=2, max_length=255)
    icai_firm_registration_number: str = Field(..., min_length=3, max_length=50)
    primary_ca_name: str = Field(..., min_length=2, max_length=255)
    icai_membership_number: str = Field(..., min_length=4, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    white_label_subdomain: Optional[str] = Field(None, max_length=63)
    primary_color: str = Field(default="#534AB7", max_length=7)

    @field_validator("icai_firm_registration_number")
    @classmethod
    def validate_firm_reg(cls, v: str) -> str:
        normalized = v.strip().upper()
        if not _ICAI_FIRM_PATTERN.match(normalized):
            raise ValueError("ICAI firm registration number must be 3–20 alphanumeric characters")
        return normalized

    @field_validator("white_label_subdomain")
    @classmethod
    def validate_subdomain(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().lower()
        if not _SUBDOMAIN_PATTERN.match(normalized):
            raise ValueError(
                "Subdomain must be 3–63 lowercase alphanumeric characters (hyphens allowed, "
                "cannot start or end with hyphen)"
            )
        return normalized

    @field_validator("primary_color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not _HEX_COLOR_PATTERN.match(v):
            raise ValueError("primary_color must be a valid hex color (e.g. #534AB7)")
        return v


class CAFirmUpdate(BaseModel):
    firm_name: Optional[str] = Field(None, min_length=2, max_length=255)
    primary_ca_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    state: Optional[str] = Field(None, min_length=2, max_length=100)
    white_label_subdomain: Optional[str] = Field(None, max_length=63)
    primary_color: Optional[str] = Field(None, max_length=7)

    @field_validator("white_label_subdomain")
    @classmethod
    def validate_subdomain(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().lower()
        if not _SUBDOMAIN_PATTERN.match(normalized):
            raise ValueError(
                "Subdomain must be 3–63 lowercase alphanumeric characters (hyphens allowed)"
            )
        return normalized

    @field_validator("primary_color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not _HEX_COLOR_PATTERN.match(v):
            raise ValueError("primary_color must be a valid hex color (e.g. #534AB7)")
        return v


class CAFirmResponse(BaseModel):
    id: uuid.UUID
    owner_user_id: uuid.UUID
    firm_name: str
    icai_firm_registration_number: str
    primary_ca_name: str
    icai_membership_number: str
    phone: Optional[str]
    city: str
    state: str
    white_label_subdomain: Optional[str]
    logo_s3_key: Optional[str]
    primary_color: str
    is_active: bool
    total_clients: int
    total_referral_earnings: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class AddClientRequest(BaseModel):
    gstin: str = Field(..., min_length=15, max_length=15)
    commission_rate: Decimal = Field(default=Decimal("0.15"), ge=0, le=0.50)

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, v: str) -> str:
        normalized = v.strip().upper()
        if len(normalized) != 15:
            raise ValueError("GSTIN must be exactly 15 characters")
        return normalized


class CAClientResponse(BaseModel):
    id: uuid.UUID
    ca_firm_id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    organization_gstin: str
    status: str
    referral_commission_rate: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralCommissionResponse(BaseModel):
    id: uuid.UUID
    ca_firm_id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    payment_id: uuid.UUID
    commission_amount: Decimal
    commission_rate: Decimal
    status: str
    payout_date: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class CADashboardStats(BaseModel):
    total_clients: int
    active_clients: int
    total_commissions_pending: Decimal
    total_commissions_paid: Decimal
    total_commissions_all_time: Decimal
    commissions_this_month: Decimal
    recent_clients: list[CAClientResponse]
    recent_commissions: list[ReferralCommissionResponse]


class CommissionSummary(BaseModel):
    total_pending: Decimal
    total_paid: Decimal
    total_cancelled: Decimal
    count_pending: int
    count_paid: int


class BrandingResponse(BaseModel):
    firm_name: str
    primary_ca_name: str
    city: str
    state: str
    primary_color: str
    logo_s3_key: Optional[str]
    white_label_subdomain: str
