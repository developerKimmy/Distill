"""글로벌 배치 및 알림 태스크"""
import asyncio
import time
from datetime import datetime

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.batch.service import GlobalBatchService
from app.settings.service import UserSettingsService
from app.common.utils import EmailService


@celery_app.task(bind=True, name="app.tasks.batch.run_global_batch")
def run_global_batch(self, triggered_by: str = "scheduled"):
    """글로벌 배치 실행 (모든 유저 공유)"""
    print(f"[TASK] Global batch started, triggered_by: {triggered_by}")
    start = time.time()
    result = asyncio.run(_run_global_batch(triggered_by))
    duration = time.time() - start
    print(f"[TASK] Global batch completed in {duration:.2f}s")
    return result


async def _run_global_batch(triggered_by: str):
    """비동기 글로벌 배치 실행"""
    async with AsyncSessionLocal() as db:
        service = GlobalBatchService(db)
        batch_run = await service.run(triggered_by=triggered_by)

        return {
            "batch_run_id": str(batch_run.id),
            "status": batch_run.status,
            "issues_created": batch_run.issues_created
        }


@celery_app.task(bind=True, name="app.tasks.batch.send_scheduled_notifications")
def send_scheduled_notifications(self):
    """현재 시간에 알림 받을 유저들에게 이메일 발송"""
    print(f"[TASK] Checking scheduled notifications...")
    result = asyncio.run(_send_scheduled_notifications())
    print(f"[TASK] Notification check completed: {result}")
    return result


async def _send_scheduled_notifications():
    """비동기 알림 발송"""
    async with AsyncSessionLocal() as db:
        current_time = datetime.now().strftime("%H:%M")

        # 최근 완료된 배치 조회
        batch_service = GlobalBatchService(db)
        batch_run = await batch_service.get_latest_completed_batch()

        if not batch_run:
            return {"sent_count": 0, "message": "No completed batch found"}

        # 현재 시간에 알림 받을 유저 조회
        settings_service = UserSettingsService(db)
        users = await settings_service.get_users_for_notification(current_time)

        if not users:
            return {"sent_count": 0, "checked_at": current_time, "message": "No users to notify"}

        # 이메일 발송
        sent_count = 0
        if settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD:
            email_service = EmailService(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)

            duration = (batch_run.completed_at - batch_run.started_at).total_seconds() if batch_run.completed_at else 0

            for user in users:
                try:
                    email_service.send_batch_complete(
                        recipient=user.email,
                        issues_count=batch_run.issues_created,
                        duration_seconds=duration,
                        success_count=batch_run.issues_created,
                        fail_count=0
                    )
                    sent_count += 1
                    print(f"[NOTIFICATION] Sent to {user.email}")
                except Exception as e:
                    print(f"[NOTIFICATION] Failed to send to {user.email}: {e}")

        return {
            "sent_count": sent_count,
            "checked_at": current_time,
            "batch_run_id": str(batch_run.id)
        }
