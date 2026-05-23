import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_client_ip,
    get_current_user,
    get_db_session,
    get_user_agent,
)
from app.core.config import settings
from app.core.exceptions import AuthenticationError, ValidationError
from app.core.security import add_user_to_blocklist, remove_user_from_blocklist, create_access_token, create_refresh_token, generate_secure_token, hash_password, verify_password
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    OrganizationResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    UserWithOrgResponse,
    _validate_password,
)
from app.schemas.common import ApiResponse, make_response
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=ApiResponse[AuthResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account and organisation in a single transaction.",
)
async def register(
    request_body: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
    ip: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
) -> ApiResponse[AuthResponse]:
    service = AuthService(db)
    user, org = await service.register(request=request_body, ip_address=ip)

    access_token = create_access_token(
        user_id=str(user.id),
        org_id=str(org.id),
        role=user.account_type.value,
    )
    refresh_token = create_refresh_token(user_id=str(user.id))
    await service.store_refresh_token(user.id, refresh_token)
    await db.commit()

    return make_response(
        AuthResponse(
            tokens=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=settings.access_token_expire_seconds,
            ),
            user=UserWithOrgResponse(
                user=UserResponse.model_validate(user),
                organization=OrganizationResponse.model_validate(org),
            ),
        )
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=ApiResponse[AuthResponse],
    status_code=status.HTTP_200_OK,
    summary="Login",
    description="Authenticate with email and password. Brute-force protection active.",
)
async def login(
    request_body: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
    ip: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
) -> ApiResponse[AuthResponse]:
    service = AuthService(db)
    user, org = await service.login(
        request=request_body,
        ip_address=ip,
        user_agent=user_agent,
    )

    access_token = create_access_token(
        user_id=str(user.id),
        org_id=str(org.id),
        role=user.account_type.value,
    )
    refresh_token = create_refresh_token(user_id=str(user.id))
    await service.store_refresh_token(user.id, refresh_token)
    await remove_user_from_blocklist(str(user.id))
    await db.commit()

    return make_response(
        AuthResponse(
            tokens=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=settings.access_token_expire_seconds,
            ),
            user=UserWithOrgResponse(
                user=UserResponse.model_validate(user),
                organization=OrganizationResponse.model_validate(org),
            ),
        )
    )


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Issue a new token pair. The old refresh token is invalidated (rotation).",
)
async def refresh(
    request_body: RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[TokenResponse]:
    service = AuthService(db)
    new_access, new_refresh = await service.refresh_tokens(
        refresh_token=request_body.refresh_token,
    )
    await db.commit()
    return make_response(
        TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in=settings.access_token_expire_seconds,
        )
    )


# ---------------------------------------------------------------------------
# Me
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=ApiResponse[UserWithOrgResponse],
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Return authenticated user details and their organisation.",
)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[UserWithOrgResponse]:
    service = AuthService(db)
    user, org = await service.get_user_with_org(user_id=current_user.id)
    return make_response(
        UserWithOrgResponse(
            user=UserResponse.model_validate(user),
            organization=OrganizationResponse.model_validate(org),
        )
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@router.post(
    "/logout",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Logout",
    description="Invalidate session. Frontend must discard stored tokens.",
)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    service = AuthService(db)
    await service._create_audit_log(
        action="user_logged_out",
        user_id=current_user.id,
    )
    # Immediately invalidate access tokens for this user.
    await add_user_to_blocklist(str(current_user.id))
    await db.commit()
    return make_response({"message": "Logged out successfully"})


# ---------------------------------------------------------------------------
# Forgot password
# ---------------------------------------------------------------------------


@router.post(
    "/forgot-password",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Send a password-reset email. Always returns 200 to prevent enumeration.",
)
async def forgot_password(
    request_body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    service = AuthService(db)
    await service.request_password_reset(email=str(request_body.email))
    return make_response(
        {
            "message": (
                "If this email is registered, "
                "you will receive reset instructions shortly."
            )
        }
    )


# ---------------------------------------------------------------------------
# Reset password
# ---------------------------------------------------------------------------


@router.post(
    "/reset-password",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Reset password",
    description="Complete password reset with the token received by email.",
)
async def reset_password(
    request_body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    service = AuthService(db)
    await service.reset_password(
        token=request_body.token,
        new_password=request_body.new_password,
    )
    return make_response({"message": "Password reset successfully. Please log in."})


# ---------------------------------------------------------------------------
# Verify email
# ---------------------------------------------------------------------------


@router.get(
    "/verify-email",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
    description="Confirm email ownership using the token sent at registration.",
)
async def verify_email(
    token: str = Query(..., description="Verification token from email link"),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    from app.models.user import User as _User

    hashed = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(_User).where(_User.email_verification_token == hashed)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise ValidationError(
            message="Invalid or expired verification link.",
            code="VAL_007",
        )

    if user.is_verified:
        return make_response({"message": "Email already verified. You can log in."})

    user.is_verified = True
    user.email_verification_token = None
    db.add(AuditLog(action="email_verified", user_id=user.id))
    await db.commit()

    return make_response({"message": "Email verified successfully. You can now log in."})


# ---------------------------------------------------------------------------
# Change password (authenticated)
# ---------------------------------------------------------------------------

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password(v)


@router.post(
    "/change-password",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Change password",
)
async def change_password(
    request_body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    if not verify_password(request_body.current_password, current_user.hashed_password):
        raise AuthenticationError.invalid_credentials()

    current_user.hashed_password = hash_password(request_body.new_password)
    db.add(AuditLog(action="password_changed", user_id=current_user.id))
    await db.commit()
    return make_response({"message": "Password changed successfully."})


# ---------------------------------------------------------------------------
# Delete account (DPDP Act compliance)
# ---------------------------------------------------------------------------

class DeleteAccountRequest(BaseModel):
    confirmation: str


@router.delete(
    "/me",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Delete account",
)
async def delete_account(
    request_body: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    from sqlalchemy import delete as sa_delete
    from app.models.refresh_token import RefreshToken as RT
    from app.models.user_preferences import UserPreferences

    if request_body.confirmation != "DELETE":
        raise ValidationError(
            message="Confirmation must be exactly 'DELETE'.",
            code="VAL_010",
        )

    # Anonymise personal data (soft delete)
    uid = current_user.id
    current_user.is_active = False
    current_user.email = f"deleted_{uid}@deleted.gstsense.in"
    current_user.full_name = "Deleted User"
    current_user.phone = None
    current_user.hashed_password = hash_password(generate_secure_token(16))

    # Revoke all refresh tokens
    await db.execute(sa_delete(RT).where(RT.user_id == uid))

    # Delete preferences
    await db.execute(sa_delete(UserPreferences).where(UserPreferences.user_id == uid))

    db.add(AuditLog(action="account_deleted", user_id=uid))
    await db.commit()

    await add_user_to_blocklist(str(uid))

    return make_response({"message": "Your account has been scheduled for deletion."})


# ---------------------------------------------------------------------------
# Update profile (authenticated)
# ---------------------------------------------------------------------------

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 2 or len(v) > 100:
                raise ValueError("full_name must be between 2 and 100 characters")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 20:
            raise ValueError("phone must be at most 20 characters")
        return v


@router.patch(
    "/me",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Update profile",
)
async def update_profile(
    request_body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[UserResponse]:
    if request_body.full_name is not None:
        current_user.full_name = request_body.full_name
    if request_body.phone is not None:
        current_user.phone = request_body.phone if request_body.phone else None

    db.add(AuditLog(action="profile_updated", user_id=current_user.id))
    await db.commit()
    await db.refresh(current_user)
    return make_response(UserResponse.model_validate(current_user))
