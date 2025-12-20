from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import SettingsService
from app.schemas import (
    SettingsResponse,
    SettingsUpdateRequest,
    CategorySettings,
    NotificationSettings,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    """설정 조회"""
    service = SettingsService(db)
    settings = service.get()

    return SettingsResponse(
        categories=settings["categories"],
        notification=settings["notification"]
    )


@router.put("", response_model=SettingsResponse)
def update_settings(
        request: SettingsUpdateRequest,
        db: Session = Depends(get_db)
):
    """설정 변경"""
    service = SettingsService(db)
    settings = service.update(
        categories=request.categories,
        notification=request.notification
    )

    return SettingsResponse(
        categories=settings["categories"],
        notification=settings["notification"]
    )