from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "dstill",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    # 글로벌 배치 실행 (하루 3회: 06:00, 12:00, 18:00)
    "run-global-batch-morning": {
        "task": "app.tasks.batch.run_global_batch",
        "schedule": crontab(hour=6, minute=0),
        "args": ("scheduled",)
    },
    "run-global-batch-noon": {
        "task": "app.tasks.batch.run_global_batch",
        "schedule": crontab(hour=12, minute=0),
        "args": ("scheduled",)
    },
    "run-global-batch-evening": {
        "task": "app.tasks.batch.run_global_batch",
        "schedule": crontab(hour=18, minute=0),
        "args": ("scheduled",)
    },
    # 이메일 알림 체크 (매 30분)
    "send-scheduled-notifications": {
        "task": "app.tasks.batch.send_scheduled_notifications",
        "schedule": crontab(minute="0,30"),
    },
}

celery_app.autodiscover_tasks(["app.tasks"])
