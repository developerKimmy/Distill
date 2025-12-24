import time
from datetime import datetime
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.batch.models import BatchRun
from app.workspace.models import Workspace
from app.issues.service import IssueService


class BatchService:
    """배치 실행 관리 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.issue_service = IssueService(db)

    async def get_workspace_by_user(self, user_id: UUID) -> Workspace:
        """사용자의 워크스페이스 조회"""
        stmt = select(Workspace).where(Workspace.user_id == user_id)
        result = await self.db.execute(stmt)
        workspace = result.scalar_one_or_none()

        if not workspace:
            raise ValueError("Workspace not found for user")

        return workspace

    async def start(self, user_id: UUID, schedule: str | None = None) -> Workspace:
        """배치 활성화"""
        workspace = await self.get_workspace_by_user(user_id)
        workspace.is_active = True

        if schedule:
            workspace.schedule = schedule

        await self.db.commit()
        await self.db.refresh(workspace)
        return workspace

    async def stop(self, user_id: UUID) -> Workspace:
        """배치 비활성화"""
        workspace = await self.get_workspace_by_user(user_id)
        workspace.is_active = False
        await self.db.commit()
        await self.db.refresh(workspace)
        return workspace

    async def update_schedule(self, user_id: UUID, schedule: str) -> Workspace:
        """스케줄 변경"""
        workspace = await self.get_workspace_by_user(user_id)
        workspace.schedule = schedule
        await self.db.commit()
        await self.db.refresh(workspace)
        return workspace

    async def get_status(self, user_id: UUID) -> dict:
        """배치 상태 조회"""
        workspace = await self.get_workspace_by_user(user_id)

        result = await self.db.execute(
            select(func.count(BatchRun.id))
            .where(BatchRun.workspace_id == workspace.id)
        )
        total_runs = result.scalar()

        return {
            "is_active": workspace.is_active,
            "schedule": workspace.schedule,
            "last_run_at": workspace.last_run_at,
            "total_runs": total_runs
        }

    async def run(self, user_id: UUID, triggered_by: str = "manual") -> BatchRun:
        """배치 실행 (이슈 수집)"""
        print(f"[SERVICE] BatchService.run started for user: {user_id}")
        start = time.time()
        workspace = await self.get_workspace_by_user(user_id)
        print(f"[SERVICE] Workspace found: {workspace.id}")
        batch_run = BatchRun(
            workspace_id=workspace.id,
            status="started",
            triggered_by=triggered_by,
            started_at=datetime.utcnow()
        )
        self.db.add(batch_run)
        await self.db.commit()
        await self.db.refresh(batch_run)

        try:
            print(f"[SERVICE] Starting issue collection...")
            issues = await self.issue_service.collect_issues(batch_run_id=batch_run.id)
            print(f"[SERVICE] Issue collection completed, {len(issues)} issues created")

            batch_run.status = "completed"
            batch_run.completed_at = datetime.utcnow()
            batch_run.issues_created = len(issues)

            workspace.last_run_at = datetime.utcnow()

        except Exception as e:
            print(f"[SERVICE] Error during batch run: {e}")
            batch_run.status = "failed"
            batch_run.completed_at = datetime.utcnow()
            batch_run.error_message = str(e)

        await self.db.commit()
        await self.db.refresh(batch_run)
        print(f"[SERVICE] BatchService.run completed in {time.time() - start:.2f}s")
        return batch_run