from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_async_session
from app.core.config import settings
from app.batch.service import GlobalBatchService
from app.batch.schemas import GlobalBatchStatusResponse, BatchTaskResponse
from app.auth.models import User
from app.auth.router import current_active_user


router = APIRouter(prefix="/batch", tags=["batch"])


def verify_cron_secret(x_cron_secret: Optional[str] = Header(None)):
    """Cron job 요청 검증 (선택적)"""
    cron_secret = getattr(settings, 'CRON_SECRET', None)
    if cron_secret and x_cron_secret != cron_secret:
        raise HTTPException(status_code=403, detail="Invalid cron secret")
    return True


@router.get("/status", response_model=GlobalBatchStatusResponse)
async def get_global_batch_status(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """글로벌 배치 상태 조회 (read-only)"""
    service = GlobalBatchService(db)
    status = await service.get_status()

    return GlobalBatchStatusResponse(
        schedule=status["schedule"],
        last_run_at=status["last_run_at"],
        total_runs=status["total_runs"],
        last_issues_created=status["last_issues_created"]
    )


@router.post("/run", response_model=BatchTaskResponse)
async def run_batch_now(
    user: User = Depends(current_active_user)
):
    """배치 수동 실행 (개발/테스트용)"""
    from app.tasks.batch import run_global_batch

    print(f"[BATCH] /run endpoint called by user: {user.id}")
    task = run_global_batch.delay("manual")
    print(f"[BATCH] Task queued with id: {task.id}")

    return BatchTaskResponse(
        task_id=task.id,
        status="queued"
    )


@router.post("/run/cron", response_model=BatchTaskResponse)
async def run_batch_cron(
    _: bool = Depends(verify_cron_secret)
):
    """배치 실행 (Render Cron용, 인증 불필요)"""
    from app.tasks.batch import run_global_batch

    task = run_global_batch.delay("scheduled")

    return BatchTaskResponse(
        task_id=task.id,
        status="queued"
    )


@router.post("/notifications/send", response_model=BatchTaskResponse)
async def send_notifications_cron(
    _: bool = Depends(verify_cron_secret)
):
    """알림 발송 (Render Cron용, 인증 불필요)"""
    from app.tasks.batch import send_scheduled_notifications

    task = send_scheduled_notifications.delay()

    return BatchTaskResponse(
        task_id=task.id,
        status="queued"
    )


@router.post("/agent/run", response_model=BatchTaskResponse)
async def run_agent_cron(
    _: bool = Depends(verify_cron_secret)
):
    """Agent 실행 (테스트/Cron용, 인증 불필요)"""
    from app.tasks.agent import run_agent_cycle

    task = run_agent_cycle.delay()

    return BatchTaskResponse(
        task_id=task.id,
        status="queued"
    )
