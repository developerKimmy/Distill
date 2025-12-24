from datetime import datetime
from pydantic import Field, field_validator

from app.common.schema import BaseSchema


class BatchSchedule(BaseSchema):
    """배치 스케줄 설정"""
    times: list[str] = Field(
        default=["09:00", "18:00"],
        description="실행 시간 목록 (HH:00 또는 HH:30 형식)"
    )
    timezone: str = Field(default="Asia/Seoul")

    @field_validator("times")
    @classmethod
    def validate_times(cls, v: list[str]) -> list[str]:
        for time in v:
            if len(time) != 5 or time[2] != ":":
                raise ValueError(f"Invalid time format: {time}. Use HH:MM")

            hour, minute = time.split(":")
            if not (0 <= int(hour) <= 23):
                raise ValueError(f"Invalid hour: {hour}")
            if minute not in ("00", "30"):
                raise ValueError(f"Minutes must be 00 or 30, got: {minute}")

        return v


class BatchStartRequest(BaseSchema):
    """배치 시작 요청"""
    schedule: BatchSchedule | None = None


class BatchScheduleUpdateRequest(BaseSchema):
    """스케줄 변경 요청"""
    schedule: BatchSchedule


class BatchStatusResponse(BaseSchema):
    """배치 상태 응답"""
    is_active: bool
    schedule: BatchSchedule | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    total_runs: int


class BatchRunResponse(BaseSchema):
    """배치 실행 결과"""
    batch_run_id: str
    status: str
    issues_created: int
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None


class BatchTaskResponse(BaseSchema):
    """배치 태스크 시작 응답"""
    task_id: str
    status: str = "queued"