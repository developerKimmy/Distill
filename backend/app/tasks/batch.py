# app/tasks/batch.py
import asyncio
import time
from uuid import UUID

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.batch.service import BatchService
from app.auth.models import User
from app.common.utils import EmailService


@celery_app.task(bind=True, name="app.tasks.batch.run_batch_task")
def run_batch_task(self, user_id: str, triggered_by: str = "manual"):
    """배치 실행 태스크"""
    print(f"[TASK] Celery task started for user: {user_id}, triggered_by: {triggered_by}")
    start = time.time()
    result = asyncio.run(_run_batch(user_id, triggered_by))
    duration = time.time() - start
    print(f"[TASK] Celery task completed in {duration:.2f}s")

    # 이메일 알림 발송 (user 이메일로)
    user_email = result.get("user_email")
    if user_email and settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD:
        email_service = EmailService(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
        email_service.send_batch_complete(
            recipient=user_email,
            issues_count=result.get("issues_created", 0),
            duration_seconds=duration,
            success_count=result.get("issues_created", 0),
            fail_count=0
        )

    return result


async def _run_batch(user_id: str, triggered_by: str):
    """실제 비동기 배치 실행"""
    print(f"[TASK] _run_batch started")
    start = time.time()
    async with AsyncSessionLocal() as db:
        # 사용자 이메일 조회
        user_result = await db.execute(
            select(User.email).where(User.id == UUID(user_id))
        )
        user_email = user_result.scalar_one_or_none()

        service = BatchService(db)
        batch_run = await service.run(
            user_id=UUID(user_id),
            triggered_by=triggered_by
        )
        print(f"[TASK] _run_batch completed in {time.time() - start:.2f}s")
        return {
            "batch_run_id": str(batch_run.id),
            "status": batch_run.status,
            "issues_created": batch_run.issues_created,
            "user_email": user_email
        }


@celery_app.task(bind=True, name="app.tasks.batch.check_and_run_scheduled")
def check_and_run_scheduled(self):
    """스케줄된 배치 체크 및 실행"""
    return asyncio.run(_check_and_run_scheduled())


async def _check_and_run_scheduled():
    """실제 비동기 스케줄 체크"""
    from datetime import datetime
    from sqlalchemy import select
    from app.workspace.models import Workspace

    async with AsyncSessionLocal() as db:
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        stmt = select(Workspace).where(
            Workspace.is_active == True,
            Workspace.schedule.contains(current_time)
        )
        result = await db.execute(stmt)
        workspaces = result.scalars().all()

        triggered_count = 0
        for workspace in workspaces:
            run_batch_task.delay(str(workspace.user_id), "scheduled")
            triggered_count += 1

        return {
            "checked_at": current_time,
            "triggered_count": triggered_count
        }