from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "atlas",
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
    "check-scheduled-batches": {
        "task": "app.tasks.batch.check_and_run_scheduled",
        "schedule": crontab(minute="0,30"),
    },
}

celery_app.autodiscover_tasks(["app.tasks"])