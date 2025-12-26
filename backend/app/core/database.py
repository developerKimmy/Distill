from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import Generator, AsyncGenerator
import ssl

from app.core.config import settings


def get_database_urls():
    """DATABASE_URL을 sync/async 버전으로 변환"""
    db_url = settings.DATABASE_URL

    # asyncpg용 URL (sslmode 제거, ssl은 connect_args로 전달)
    async_url = db_url
    if "+asyncpg" not in async_url:
        async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")

    # sslmode=require 가 있는지 확인
    needs_ssl = "sslmode=require" in async_url or "sslmode=verify" in async_url

    # asyncpg URL에서 sslmode 제거 (asyncpg는 sslmode 파라미터를 지원하지 않음)
    if "sslmode=" in async_url:
        # URL에서 sslmode 파라미터 제거
        import re
        async_url = re.sub(r'[?&]sslmode=[^&]*', '', async_url)
        async_url = async_url.replace('?&', '?').rstrip('?')

    # sync용 URL (psycopg2)
    sync_url = db_url.replace("+asyncpg", "")
    if sync_url.startswith("postgres://"):
        sync_url = sync_url.replace("postgres://", "postgresql://", 1)

    return sync_url, async_url, needs_ssl


SYNC_DATABASE_URL, ASYNC_DATABASE_URL, NEEDS_SSL = get_database_urls()

# 동기 엔진 (psycopg2)
engine = create_engine(
    SYNC_DATABASE_URL,
    pool_pre_ping=True,  # 커넥션 사용 전 유효성 체크
    pool_recycle=300,    # 5분마다 커넥션 재생성
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """동기 DB 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 비동기 엔진 (asyncpg)
# SSL이 필요하면 connect_args로 전달
connect_args = {}
if NEEDS_SSL:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_context

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    connect_args=connect_args,
)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """비동기 DB 세션 의존성"""
    async with AsyncSessionLocal() as session:
        yield session
