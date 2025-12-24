from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.batch.service import BatchService
from app.batch.schemas import (
    BatchStartRequest,
    BatchScheduleUpdateRequest,
    BatchStatusResponse,
    BatchTaskResponse,
    BatchSchedule
)
from app.auth.models import User
from app.auth.router import current_active_user


router = APIRouter(prefix="/batch", tags=["batch"])


@router.post("/start", response_model=BatchStatusResponse)
async def start_batch(
        request: BatchStartRequest = None,
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
):
    """배치 활성화 (스케줄 등록)"""
    service = BatchService(db)
    schedule = None
    if request and request.schedule:
        schedule = ",".join(request.schedule.times)

    await service.start(user_id=user.id, schedule=schedule)
    status = await service.get_status(user_id=user.id)

    return BatchStatusResponse(
        is_active=status["is_active"],
        schedule=request.schedule if request else None,
        last_run_at=status["last_run_at"],
        next_run_at=None,
        total_runs=status["total_runs"]
    )


@router.post("/stop", response_model=BatchStatusResponse)
async def stop_batch(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """배치 비활성화"""
    service = BatchService(db)
    await service.stop(user_id=user.id)
    status = await service.get_status(user_id=user.id)

    return BatchStatusResponse(
        is_active=status["is_active"],
        schedule=None,
        last_run_at=status["last_run_at"],
        next_run_at=None,
        total_runs=status["total_runs"]
    )


@router.put("/schedule", response_model=BatchStatusResponse)
async def update_schedule(
    request: BatchScheduleUpdateRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """스케줄 변경"""
    service = BatchService(db)
    schedule = ",".join(request.schedule.times)
    await service.update_schedule(user_id=user.id, schedule=schedule)
    status = await service.get_status(user_id=user.id)

    return BatchStatusResponse(
        is_active=status["is_active"],
        schedule=request.schedule,
        last_run_at=status["last_run_at"],
        next_run_at=None,
        total_runs=status["total_runs"]
    )


@router.get("/status", response_model=BatchStatusResponse)
async def get_status(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """배치 상태 조회"""
    service = BatchService(db)
    status = await service.get_status(user_id=user.id)

    schedule = None
    if status.get("schedule"):
        times = status["schedule"].split(",")
        schedule = BatchSchedule(times=times)

    return BatchStatusResponse(
        is_active=status["is_active"],
        schedule=schedule,
        last_run_at=status["last_run_at"],
        next_run_at=None,
        total_runs=status["total_runs"]
    )


@router.post("/run", response_model=BatchTaskResponse)
async def run_batch(
        user: User = Depends(current_active_user)
):
    """배치 즉시 실행 (수동)"""
    from app.tasks.batch import run_batch_task  # Lazy import to avoid circular dependency

    print(f"[BATCH] /run endpoint called for user: {user.id}")
    task = run_batch_task.delay(str(user.id), "manual")
    print(f"[BATCH] Task queued with id: {task.id}")


    return BatchTaskResponse(
        task_id=task.id,
        status="queued"
    )