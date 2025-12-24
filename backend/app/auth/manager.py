from uuid import UUID
from typing import Optional
from fastapi import Depends, Request, Response
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.auth.models import User
from app.core.database import get_async_session, AsyncSessionLocal
from app.core.config import settings
from app.workspace.models import Workspace


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY

    async def _create_workspace(self, user_id: UUID) -> None:
        """Workspace 생성 및 has_workspace 플래그 업데이트 (단일 트랜잭션)"""
        async with AsyncSessionLocal() as session:
            workspace = Workspace(
                user_id=user_id,
                schedule="09:00,18:00",
                is_active=False,
                timezone="Asia/Seoul",
                notification_enabled=True
            )
            session.add(workspace)

            await session.execute(
                update(User).where(User.id == user_id).values(has_workspace=True)
            )

            await session.commit()

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

        try:
            await self._create_workspace(user.id)
            print(f"Workspace created for user {user.id}")
        except Exception as e:
            print(f"Failed to create workspace for user {user.id}: {e}")

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response: Optional[Response] = None
    ):
        if user.has_workspace:
            return

        try:
            await self._create_workspace(user.id)
            print(f"Workspace created on login for user {user.id} (fail-safe)")
        except Exception as e:
            print(f"Failed to create workspace on login for user {user.id}: {e}")


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)