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
    # Agent 사이클 실행 (매 정시, 1시간마다)
    # 뉴스 수집 → 클러스터링 → 이벤트 감지 → 즉시 알림
    "run-agent-cycle": {
        "task": "app.tasks.agent.run_agent_cycle",
        "schedule": crontab(minute=0),  # 매 정시
    },
    # 글로벌 배치 실행 (하루 3회: 06:00, 12:00, 18:00)
    # 콘텐츠 생성 (요약, 타임라인 등) 담당
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
}

celery_app.autodiscover_tasks(["app.tasks"])
