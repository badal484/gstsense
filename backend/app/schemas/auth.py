import re
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, field_validator, model_validator

GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)


def _validate_password(v: str) -> str:
    """Shared password rule enforcement used by RegisterRequest and ResetPasswordRequest."""
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if len(v) > 128:
        raise ValueError("Password must be at most 128 characters long")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit")
    return v


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    gstin: str

    @field_validator("full_name", mode="before")
    @classmethod
    def validate_full_name(cls, v: Any) -> str:
        stripped = str(v).strip()
        if len(stripped) < 2:
            raise ValueError("Full name must be at least 2 characters long")
        if len(stripped) > 100:
            raise ValueError("Full name must be at most 100 characters long")
        return stripped

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: Any) -> str:
        return str(v).lower().strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("gstin", mode="before")
    @classmethod
    def validate_gstin(cls, v: Any) -> str:
        normalized = str(v).strip().upper()
        if not GSTIN_PATTERN.match(normalized):
            raise ValueError(
                "Invalid GSTIN format. Expected format: 22AAAAA0000A1Z5 (15 characters)"
            )
        return normalized


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: Any) -> str:
        return str(v).lower().strip()

    @field_validator("password", mode="before")
    @classmethod
    def validate_password_not_empty(cls, v: Any) -> str:
        s = str(v)
        if not s:
            raise ValueError("Password must not be empty")
        if len(s) > 128:
            raise ValueError("Password must be at most 128 characters long")
        return s


class RefreshRequest(BaseModel):
    refresh_token: str

    @field_validator("refresh_token", mode="before")
    @classmethod
    def not_empty(cls, v: Any) -> str:
        s = str(v).strip()
        if not s:
            raise ValueError("refresh_token must not be empty")
        return s


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: Any) -> str:
        return str(v).lower().strip()


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("token", mode="before")
    @classmethod
    def not_empty(cls, v: Any) -> str:
        s = str(v).strip()
        if not s:
            raise ValueError("token must not be empty")
        return s

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password(v)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: Optional[str]
    account_type: str
    is_active: bool
    is_verified: bool
    created_at: str  # ISO 8601 string

    model_config = {"from_attributes": True}

    @field_validator("created_at", mode="before")
    @classmethod
    def serialize_created_at(cls, v: Any) -> str:
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)

    @field_validator("account_type", mode="before")
    @classmethod
    def enum_to_str(cls, v: Any) -> str:
        return str(v.value) if hasattr(v, "value") else str(v)


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    business_name: str
    gstin: str
    state_code: str
    plan: str
    subscription_status: str
    invoice_limit: int
    invoices_used_this_month: int
    has_active_subscription: bool
    is_invoice_limit_reached: bool = False
    billing_cycle_start: Optional[str] = None
    billing_cycle_end: Optional[str] = None

    model_config = {"from_attributes": True}

    @field_validator("plan", "subscription_status", mode="before")
    @classmethod
    def enum_to_str(cls, v: Any) -> str:
        return str(v.value) if hasattr(v, "value") else str(v)

    @field_validator("billing_cycle_start", "billing_cycle_end", mode="before")
    @classmethod
    def date_to_str(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)

    @model_validator(mode="after")
    def compute_limit_reached(self) -> "OrganizationResponse":
        if self.invoice_limit > 0:
            self.is_invoice_limit_reached = self.invoices_used_this_month >= self.invoice_limit
        return self


class UserWithOrgResponse(BaseModel):
    user: UserResponse
    organization: OrganizationResponse


class AuthResponse(BaseModel):
    tokens: TokenResponse
    user: UserWithOrgResponse
