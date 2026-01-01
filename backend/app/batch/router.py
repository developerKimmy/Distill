from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_async_session
from app.core.config import settings
from app.batch.models import BatchRun
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
    """배치 상태 조회 (히스토리용)"""
    # 총 실행 횟수
    result = await db.execute(select(func.count(BatchRun.id)))
    total_runs = result.scalar()

    # 마지막 완료된 배치
    result = await db.execute(
        select(BatchRun)
        .where(BatchRun.status == "completed")
        .order_by(BatchRun.completed_at.desc())
        .limit(1)
    )
    last_batch = result.scalar_one_or_none()

    return GlobalBatchStatusResponse(
        schedule=["Agent runs at 0,5,10,15,20h KST"],
        last_run_at=last_batch.completed_at if last_batch else None,
        total_runs=total_runs,
        last_issues_created=last_batch.issues_created if last_batch else 0
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
