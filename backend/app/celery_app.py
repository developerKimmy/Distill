from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "atlas",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1시간 타임아웃
)

# Beat 스케줄 (모니터링 자동화용)
celery_app.conf.beat_schedule = {
    # 예시: 매일 자정 모니터링 리서치 실행
    # "daily-monitoring": {
    #     "task": "app.tasks.research.run_scheduled_research",
    #     "schedule": crontab(hour=0, minute=0),
    # },
}

# 태스크 자동 발견
celery_app.autodiscover_tasks(["app.tasks"])