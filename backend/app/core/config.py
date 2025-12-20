from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Atlas"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://atlas:atlas_dev_password@localhost:5432/atlas_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # DeepSeek
    DEEPSEEK_API_KEY: str = ""

    # Tavily
    TAVILY_API_KEY: str = ""

    # YouTube
    YOUTUBE_API_KEY: str = ""

    # Naver
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()