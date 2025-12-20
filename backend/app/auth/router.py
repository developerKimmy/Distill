from fastapi import APIRouter
from fastapi_users import FastAPIUsers
from uuid import UUID

from app.auth.models import User
from app.auth.manager import get_user_manager
from app.auth.backend import auth_backend
from app.auth.schemas import UserRead, UserCreate

fastapi_users = FastAPIUsers[User, UUID](
    get_user_manager,
    [auth_backend],
)

# 현재 로그인된 사용자 의존성
current_active_user = fastapi_users.current_user(active=True)

# 라우터
router = APIRouter()

router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth",
    tags=["auth"],
)

router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)