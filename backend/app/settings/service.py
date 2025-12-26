from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.settings.models import UserSettings


class UserSettingsService:
    """유저 설정 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, user_id: UUID) -> UserSettings:
        """유저 설정 조회 또는 생성"""
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        result = await self.db.execute(stmt)
        settings = result.scalar_one_or_none()

        if not settings:
            settings = UserSettings(
                user_id=user_id,
                email_notifications_enabled=True,
                notification_times="09:00,18:00",
                timezone="Asia/Seoul"
            )
            self.db.add(settings)
            await self.db.commit()
            await self.db.refresh(settings)

        return settings

    async def get_notification_settings(self, user_id: UUID) -> dict:
        """알림 설정 조회"""
        settings = await self.get_or_create(user_id)
        times = settings.notification_times.split(",") if settings.notification_times else []
        categories = settings.category_filter.split(",") if settings.category_filter else []

        return {
            "enabled": settings.email_notifications_enabled,
            "times": times,
            "timezone": settings.timezone,
            "categories": categories,
            "created_at": settings.created_at
        }

    async def update_notification_settings(
        self,
        user_id: UUID,
        enabled: bool | None = None,
        times: list[str] | None = None,
        categories: list[str] | None = None
    ) -> UserSettings:
        """알림 설정 수정"""
        settings = await self.get_or_create(user_id)

        if enabled is not None:
            settings.email_notifications_enabled = enabled

        if times is not None:
            settings.notification_times = ",".join(times) if times else None

        if categories is not None:
            settings.category_filter = ",".join(categories) if categories else None

        await self.db.commit()
        await self.db.refresh(settings)
        return settings

    async def get_users_for_notification(self, current_time: str) -> list:
        """현재 시간에 알림 받을 유저 목록 조회"""
        from app.auth.models import User

        stmt = (
            select(User)
            .join(UserSettings)
            .where(
                UserSettings.email_notifications_enabled == True,
                UserSettings.notification_times.contains(current_time)
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
