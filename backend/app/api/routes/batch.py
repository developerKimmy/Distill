from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import BatchService
from app.schemas import (
    BatchStartRequest,
    BatchScheduleUpdateRequest,
    BatchStatusResponse,
    BatchRunResponse,
)

router = APIRouter(prefix="/batch", tags=["batch"])


@router.post("/start", response_model=BatchStatusResponse)
def start_batch(
        request: BatchStartRequest = None,
        db: Session = Depends(get_db)
):
    """배치 활성화"""
    service = BatchService(db)
    schedule = None
    if request and request.schedule:
        schedule = ",".join(request.schedule.times)

    workspace = service.start(schedule=schedule)
    status = service.get_status()

    return BatchStatusResponse(
        is_active=status["is_active"],
        schedule=request.schedule if request else None,
        last_run_at=status["last_run_at"],
        next_run_at=None,  # TODO: 계산 로직
        total_runs=status["total_runs"]
    )


@router.post("/stop", response_model=BatchStatusResponse)
def stop_batch(db: Session = Depends(get_db)):
    """배치 비활성화"""
    service = BatchService(db)
    service.stop()
    status = service.get_status()

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
        db: Session = Depends(get_db)
):
    """스케줄 변경"""
    service = BatchService(db)
    schedule = ",".join(request.schedule.times)
    service.update_schedule(schedule)
    status = service.get_status()

    return BatchStatusResponse(
        is_active=status["is_active"],
        schedule=request.schedule,
        last_run_at=status["last_run_at"],
        next_run_at=None,
        total_runs=status["total_runs"]
    )


@router.get("/status", response_model=BatchStatusResponse)
def get_status(db: Session = Depends(get_db)):
    """배치 상태 조회"""
    service = BatchService(db)
    status = service.get_status()

    return BatchStatusResponse(
        is_active=status["is_active"],
        schedule=None,  # TODO: 파싱
        last_run_at=status["last_run_at"],
        next_run_at=None,
        total_runs=status["total_runs"]
    )


@router.post("/run", response_model=BatchRunResponse)
def run_batch(db: Session = Depends(get_db)):
    """배치 수동 실행"""
    service = BatchService(db)
    batch_run = service.run()

    return BatchRunResponse(
        batch_run_id=str(batch_run.id),
        status=batch_run.status,
        issues_created=batch_run.sessions_created,
        started_at=batch_run.started_at,
        completed_at=batch_run.completed_at,
        error_message=batch_run.error_message
    )