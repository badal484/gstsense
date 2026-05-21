from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.models.user_preferences import UserPreferences
from app.schemas.common import ApiResponse, make_response

router = APIRouter(prefix="/preferences", tags=["Preferences"])


class PreferencesRequest(BaseModel):
    whatsapp_deadline_reminders: Optional[bool] = None
    whatsapp_scan_complete: Optional[bool] = None
    whatsapp_mismatch_alerts: Optional[bool] = None
    email_scan_complete: Optional[bool] = None
    email_weekly_digest: Optional[bool] = None
    email_product_updates: Optional[bool] = None


class PreferencesResponse(BaseModel):
    whatsapp_deadline_reminders: bool
    whatsapp_scan_complete: bool
    whatsapp_mismatch_alerts: bool
    email_scan_complete: bool
    email_weekly_digest: bool
    email_product_updates: bool

    model_config = {"from_attributes": True}


async def _get_or_create_prefs(user_id: object, db: AsyncSession) -> UserPreferences:
    result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == user_id)
    )
    prefs = result.scalar_one_or_none()
    if prefs is None:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
        await db.flush()
    return prefs


@router.get(
    "/",
    response_model=ApiResponse[PreferencesResponse],
    status_code=status.HTTP_200_OK,
    summary="Get notification preferences",
)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[PreferencesResponse]:
    prefs = await _get_or_create_prefs(current_user.id, db)
    await db.commit()
    return make_response(PreferencesResponse.model_validate(prefs))


@router.patch(
    "/",
    response_model=ApiResponse[PreferencesResponse],
    status_code=status.HTTP_200_OK,
    summary="Update notification preferences",
)
async def update_preferences(
    request_body: PreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[PreferencesResponse]:
    prefs = await _get_or_create_prefs(current_user.id, db)

    for field, value in request_body.model_dump(exclude_none=True).items():
        setattr(prefs, field, value)

    await db.commit()
    await db.refresh(prefs)
    return make_response(PreferencesResponse.model_validate(prefs))
