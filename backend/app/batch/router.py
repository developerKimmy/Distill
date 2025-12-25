from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.batch.service import GlobalBatchService
from app.batch.schemas import GlobalBatchStatusResponse, BatchTaskResponse
from app.auth.models import User
from app.auth.router import current_active_user


router = APIRouter(prefix="/batch", tags=["batch"])


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
