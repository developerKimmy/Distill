from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# 프로덕션에서 허용하지 않는 기본값들
INSECURE_DEFAULTS = [
    "your-secret-key-change-in-production",
    "dstill_dev_password",
]


class Settings(BaseSettings):
    # App
    APP_NAME: str = "DISTILL"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://dstill:dstill_dev_password@localhost:5432/dstill_db"

    @model_validator(mode='after')
    def validate_production_secrets(self):
        """프로덕션에서 안전하지 않은 기본값 사용 방지"""
        if not self.DEBUG:
            # SECRET_KEY 검증
            if self.SECRET_KEY in INSECURE_DEFAULTS:
                raise ValueError(
                    "프로덕션에서는 SECRET_KEY를 반드시 환경변수로 설정해야 합니다. "
                    ".env 파일에 SECRET_KEY=<안전한_랜덤_문자열> 추가하세요."
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY는 최소 32자 이상이어야 합니다.")

            # DATABASE_URL 검증
            for insecure in INSECURE_DEFAULTS:
                if insecure in self.DATABASE_URL:
                    raise ValueError(
                        "프로덕션에서는 DATABASE_URL을 반드시 환경변수로 설정해야 합니다. "
                        "기본 개발용 비밀번호를 사용하지 마세요."
                    )
        return self

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

    # CORS (쉼표로 구분, 배포 시 .env에서 설정)
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,https://kimmykim.dev"

    # Frontend URL (매직 링크 등에 사용)
    FRONTEND_URL: str = "https://kimmykim.dev"

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