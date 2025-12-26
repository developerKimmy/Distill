from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.settings.service import UserSettingsService
from app.settings.schemas import NotificationSettingsResponse, NotificationSettingsUpdateRequest
from app.auth.models import User
from app.auth.router import current_active_user


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/notifications", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """알림 설정 조회"""
    service = UserSettingsService(db)
    settings = await service.get_notification_settings(user.id)

    return NotificationSettingsResponse(
        enabled=settings["enabled"],
        times=settings["times"],
        timezone=settings["timezone"],
        categories=settings["categories"]
    )


@router.put("/notifications", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    request: NotificationSettingsUpdateRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """알림 설정 수정"""
    service = UserSettingsService(db)
    await service.update_notification_settings(
        user_id=user.id,
        enabled=request.enabled,
        times=request.times,
        categories=request.categories
    )
    settings = await service.get_notification_settings(user.id)

    return NotificationSettingsResponse(
        enabled=settings["enabled"],
        times=settings["times"],
        timezone=settings["timezone"],
        categories=settings["categories"]
    )
