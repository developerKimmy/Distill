from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import Generator, AsyncGenerator

from app.core.config import settings

# 동기 (기존 코드 호환)
SYNC_DATABASE_URL = settings.DATABASE_URL.replace("+asyncpg", "")
engine = create_engine(SYNC_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """동기 DB 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 비동기 (fastapi-users용)
async_engine = create_async_engine(settings.DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """비동기 DB 세션 의존성"""
    async with AsyncSessionLocal() as session:
        yield session