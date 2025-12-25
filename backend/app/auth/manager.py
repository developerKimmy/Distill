from uuid import UUID
from typing import Optional
from fastapi import Depends, Request, Response
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_async_session, AsyncSessionLocal
from app.core.config import settings
from app.settings.models import UserSettings


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY

    async def _create_user_settings(self, user_id: UUID) -> None:
        """UserSettings 생성 (회원가입 시 기본 설정)"""
        async with AsyncSessionLocal() as session:
            user_settings = UserSettings(
                user_id=user_id,
                email_notifications_enabled=True,
                notification_times="09:00,18:00",
                timezone="Asia/Seoul",
            )
            session.add(user_settings)
            await session.commit()

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

        try:
            await self._create_user_settings(user.id)
            print(f"UserSettings created for user {user.id}")
        except Exception as e:
            print(f"Failed to create user settings for user {user.id}: {e}")


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)
