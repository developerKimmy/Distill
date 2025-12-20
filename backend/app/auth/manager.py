from uuid import UUID
from typing import Optional
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_async_session, AsyncSessionLocal
from app.core.config import settings
from app.workspace.models import Workspace


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

        async with AsyncSessionLocal() as session:
            workspace = Workspace(
                user_id=user.id,
                schedule="09:00,18:00",
                is_active=False,
                timezone="Asia/Seoul",
                notification_enabled=True
            )
            session.add(workspace)
            await session.commit()
            print(f"Workspace created for user {user.id}")


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)