from datetime import datetime

from app.common.schema import BaseSchema


class GlobalBatchStatusResponse(BaseSchema):
    """글로벌 배치 상태 응답"""
    schedule: list[str]  # 서버 배치 시간 ["06:00", "12:00", "18:00"]
    last_run_at: datetime | None
    total_runs: int
    last_issues_created: int


class BatchTaskResponse(BaseSchema):
    """배치 태스크 시작 응답"""
    task_id: str
    status: str = "queued"
