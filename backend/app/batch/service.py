from datetime import datetime
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.batch.models import BatchRun
from app.workspace.models import Workspace
from app.issues.service import IssueService


class BatchService:
    """배치 실행 관리 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self.issue_service = IssueService(db)

    def get_workspace_by_user(self, user_id: UUID) -> Workspace:
        """사용자의 워크스페이스 조회"""
        stmt = select(Workspace).where(Workspace.user_id == user_id)
        workspace = self.db.execute(stmt).scalar_one_or_none()

        if not workspace:
            raise ValueError("Workspace not found for user")

        return workspace

    def start(self, user_id: UUID, schedule: str | None = None) -> Workspace:
        """배치 활성화"""
        workspace = self.get_workspace_by_user(user_id)
        workspace.is_active = True

        if schedule:
            workspace.schedule = schedule

        self.db.commit()
        self.db.refresh(workspace)
        return workspace

    def stop(self, user_id: UUID) -> Workspace:
        """배치 비활성화"""
        workspace = self.get_workspace_by_user(user_id)
        workspace.is_active = False
        self.db.commit()
        self.db.refresh(workspace)
        return workspace

    def update_schedule(self, user_id: UUID, schedule: str) -> Workspace:
        """스케줄 변경"""
        workspace = self.get_workspace_by_user(user_id)
        workspace.schedule = schedule
        self.db.commit()
        self.db.refresh(workspace)
        return workspace

    def get_status(self, user_id: UUID) -> dict:
        """배치 상태 조회"""
        workspace = self.get_workspace_by_user(user_id)

        total_runs = self.db.execute(
            select(func.count(BatchRun.id))
            .where(BatchRun.workspace_id == workspace.id)
        ).scalar()

        return {
            "is_active": workspace.is_active,
            "schedule": workspace.schedule,
            "last_run_at": workspace.last_run_at,
            "total_runs": total_runs
        }

    def run(self, user_id: UUID) -> BatchRun:
        """배치 실행 (이슈 수집)"""
        workspace = self.get_workspace_by_user(user_id)

        batch_run = BatchRun(
            workspace_id=workspace.id,
            status="started",
            triggered_by="manual",
            started_at=datetime.utcnow()
        )
        self.db.add(batch_run)
        self.db.commit()
        self.db.refresh(batch_run)

        try:
            issues = self.issue_service.collect_issues(batch_run_id=batch_run.id)

            batch_run.status = "completed"
            batch_run.completed_at = datetime.utcnow()
            batch_run.sessions_created = len(issues)

            workspace.last_run_at = datetime.utcnow()

        except Exception as e:
            batch_run.status = "failed"
            batch_run.completed_at = datetime.utcnow()
            batch_run.error_message = str(e)

        self.db.commit()
        self.db.refresh(batch_run)
        return batch_run