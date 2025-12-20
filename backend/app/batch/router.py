from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.batch.service import BatchService
from app.batch.schemas import (
    BatchStartRequest,
    BatchScheduleUpdateRequest,
    BatchStatusResponse,
    BatchRunResponse,
    BatchSchedule
)
from app.auth.models import User
from app.auth.router import current_active_user


router = APIRouter(prefix="/batch", tags=["batch"])


@router.post("/start", response_model=BatchStatusResponse)
def start_batch(
    request: BatchStartRequest = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user)
):
    """배치 활성화"""
    service = BatchService(db)
    schedule = None
    if request and request.schedule:
        schedule = ",".join(request.schedule.times)

    service.start(user_id=user.id, schedule=schedule)
    status = service.get_status(user_id=user.id)

    return BatchStatusResponse(
        is_active=status["is_active"],
        schedule=request.schedule if request else None,
        last_run_at=status["last_run_at"],
        next_run_at=None,
        total_runs=status["total_runs"]
    )


@router.post("/stop", response_model=BatchStatusResponse)
def stop_batch(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user)
):
    """배치 비활성화"""
    service = BatchService(db)
    service.stop(user_id=user.id)
    status = service.get_status(user_id=user.id)

    return BatchStatusResponse(
        is_active=status["is_active"],
        schedule=None,
        last_run_at=status["last_run_at"],
        next_run_at=None,
        total_runs=status["total_runs"]
    )


@router.put("/schedule", response_model=BatchStatusResponse)
def update_schedule(
    request: BatchScheduleUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user)
):
    """스케줄 변경"""
    service = BatchService(db)
    schedule = ",".join(request.schedule.times)
    service.update_schedule(user_id=user.id, schedule=schedule)
    status = service.get_status(user_id=user.id)

    return BatchStatusResponse(
        is_active=status["is_active"],
        schedule=request.schedule,
        last_run_at=status["last_run_at"],
        next_run_at=None,
        total_runs=status["total_runs"]
    )


@router.get("/status", response_model=BatchStatusResponse)
def get_status(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user)
):
    """배치 상태 조회"""
    service = BatchService(db)
    status = service.get_status(user_id=user.id)

    # DB 문자열 → BatchSchedule 객체 변환
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


@router.post("/run", response_model=BatchRunResponse)
def run_batch(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user)
):
    """배치 수동 실행"""
    service = BatchService(db)
    batch_run = service.run(user_id=user.id)

    return BatchRunResponse(
        batch_run_id=str(batch_run.id),
        status=batch_run.status,
        issues_created=batch_run.sessions_created,
        started_at=batch_run.started_at,
        completed_at=batch_run.completed_at,
        error_message=batch_run.error_message
    )