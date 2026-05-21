from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_client_ip,
    get_current_user,
    get_db_session,
    get_user_agent,
)
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
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
