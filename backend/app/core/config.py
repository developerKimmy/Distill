from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


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

    #OPENAI
    OPEN_AI_API_KEY: str = ""

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

    # Email (Gmail SMTP)
    GMAIL_USER: str = ""
    GMAIL_APP_PASSWORD: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Global Batch Schedule (하루 3회)
    BATCH_SCHEDULE: str = "06:00,12:00,18:00"

    # Cron Secret (Render Cron 요청 검증용, 선택)
    CRON_SECRET: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings(_env_file=BACKEND_DIR / ".env")


settings = get_settings()