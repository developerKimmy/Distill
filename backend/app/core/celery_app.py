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
    # 태스크 타임아웃 설정 (LLM API 호출 포함하므로 넉넉하게)
    task_time_limit=1800,  # 30분 (hard limit - SIGKILL)
    task_soft_time_limit=1500,  # 25분 (soft limit - exception)
    # Worker 설정
    worker_prefetch_multiplier=1,  # 한 번에 하나씩 처리
    task_acks_late=True,  # 완료 후 ACK (실패 시 재시도 가능)
)

celery_app.conf.beat_schedule = {
    # Agent 사이클 실행 (5시간마다: 0, 5, 10, 15, 20시)
    # 뉴스 수집 → 클러스터링 → 이벤트 감지 → 즉시 알림
    "run-agent-cycle": {
        "task": "app.tasks.agent.run_agent_cycle",
        "schedule": crontab(hour="0,5,10,15,20", minute=0),  # 5시간마다
    },
    # 아침 데일리 다이제스트 발송 (매일 오전 8시)
    # 어제 있었던 이슈를 요약해서 이메일로 발송
    "send-morning-digest": {
        "task": "app.tasks.batch.send_morning_digest",
        "schedule": crontab(hour=8, minute=0),
    },
}

celery_app.autodiscover_tasks(["app.tasks"])
