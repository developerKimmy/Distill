from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi_users import FastAPIUsers
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.manager import get_user_manager
from app.auth.backend import auth_backend, get_jwt_strategy
from app.auth.schemas import UserRead, UserCreate
from app.auth.magic_link import verify_magic_token
from app.core.database import get_async_session

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


@router.get("/auth/magic")
async def verify_magic_link(
    token: str = Query(..., description="매직 링크 토큰"),
    db: AsyncSession = Depends(get_async_session)
):
    """매직 링크 검증 및 로그인 토큰 발급"""
    # 토큰 검증
    user_id = verify_magic_token(token)
    if not user_id:
        raise HTTPException(status_code=400, detail="유효하지 않거나 만료된 링크입니다")

    # 유저 조회
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="비활성화된 계정입니다")

    # JWT 토큰 생성
    strategy = get_jwt_strategy()
    access_token = await strategy.write_token(user)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }