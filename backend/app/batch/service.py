import time
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.batch.models import BatchRun
from app.issues.service import IssueService
from app.core.config import settings


class GlobalBatchService:
    """글로벌 배치 실행 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.issue_service = IssueService(db)

    async def get_status(self) -> dict:
        """글로벌 배치 상태 조회"""
        # 총 실행 횟수
        result = await self.db.execute(select(func.count(BatchRun.id)))
        total_runs = result.scalar()

        # 마지막 완료된 배치
        result = await self.db.execute(
            select(BatchRun)
            .where(BatchRun.status == "completed")
            .order_by(BatchRun.completed_at.desc())
            .limit(1)
        )
        last_batch = result.scalar_one_or_none()

        return {
            "schedule": settings.BATCH_SCHEDULE.split(","),
            "last_run_at": last_batch.completed_at if last_batch else None,
            "total_runs": total_runs,
            "last_issues_created": last_batch.issues_created if last_batch else 0
        }

    async def run(self, triggered_by: str = "scheduled") -> BatchRun:
        """글로벌 배치 실행 (모든 유저 공유)"""
        print(f"[SERVICE] GlobalBatchService.run started, triggered_by: {triggered_by}")
        start = time.time()

        batch_run = BatchRun(
            status="started",
            triggered_by=triggered_by,
            started_at=datetime.utcnow()
        )
        self.db.add(batch_run)
        await self.db.commit()
        await self.db.refresh(batch_run)
        print(f"[SERVICE] BatchRun created: {batch_run.id}")

        try:
            print(f"[SERVICE] Starting issue collection...")
            issues = await self.issue_service.collect_issues(batch_run_id=batch_run.id)
            print(f"[SERVICE] Issue collection completed, {len(issues)} issues created")

            batch_run.status = "completed"
            batch_run.completed_at = datetime.utcnow()
            batch_run.issues_created = len(issues)

        except Exception as e:
            print(f"[SERVICE] Error during batch run: {e}")
            batch_run.status = "failed"
            batch_run.completed_at = datetime.utcnow()
            batch_run.error_message = str(e)

        await self.db.commit()
        await self.db.refresh(batch_run)
        print(f"[SERVICE] GlobalBatchService.run completed in {time.time() - start:.2f}s")
        return batch_run

    async def get_latest_completed_batch(self) -> BatchRun | None:
        """최근 완료된 배치 조회"""
        result = await self.db.execute(
            select(BatchRun)
            .where(BatchRun.status == "completed")
            .order_by(BatchRun.completed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
