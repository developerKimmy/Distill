"""배치 및 알림 Celery 태스크"""
import asyncio
import time
from datetime import datetime, timezone, timedelta

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal, SessionLocal
from app.batch.service import GlobalBatchService
from app.tasks.notifications import send_digest_notifications, send_followed_notifications

KST = timezone(timedelta(hours=9))


# ============ 배치 태스크 ============

@celery_app.task(bind=True, name="app.tasks.batch.run_global_batch")
def run_global_batch(self, triggered_by: str = "scheduled"):
    """글로벌 배치 실행"""
    print(f"[BATCH] Started, triggered_by: {triggered_by}")
    start = time.time()

    result = asyncio.run(_run_batch_async(triggered_by))

    print(f"[BATCH] Completed in {time.time() - start:.2f}s")

    # 배치 완료 시 알림 트리거
    if result.get("status") == "completed":
        _trigger_notifications(result["batch_run_id"])

    return result


async def _run_batch_async(triggered_by: str) -> dict:
    """비동기 배치 실행"""
    async with AsyncSessionLocal() as db:
        service = GlobalBatchService(db)
        batch_run = await service.run(triggered_by=triggered_by)

        return {
            "batch_run_id": str(batch_run.id),
            "status": batch_run.status,
            "issues_created": batch_run.issues_created
        }


def _trigger_notifications(batch_run_id: str) -> None:
    """배치 완료 후 알림 태스크 트리거"""
    batch_time = datetime.now(KST).strftime("%H:%M")
    print(f"[BATCH] Triggering notifications for {batch_time}")

    send_scheduled_notifications.delay(batch_time=batch_time)
    send_followed_issues_notifications.delay(batch_run_id=batch_run_id)


# ============ 알림 태스크 ============

@celery_app.task(bind=True, name="app.tasks.batch.send_scheduled_notifications")
def send_scheduled_notifications(self, batch_time: str | None = None):
    """카테고리 다이제스트 알림 발송"""
    print(f"[NOTIFICATION] Digest started (batch_time={batch_time})")

    try:
        with SessionLocal() as db:
            result = send_digest_notifications(db, batch_time)
            db.commit()
            print(f"[NOTIFICATION] Digest completed: {result.message}, sent={result.sent_count}")
            return result.to_dict()
    except Exception as e:
        print(f"[NOTIFICATION] Digest failed: {e}")
        return {"status": "failed", "error": str(e)}


@celery_app.task(bind=True, name="app.tasks.batch.send_followed_issues_notifications")
def send_followed_issues_notifications(self, batch_run_id: str):
    """팔로우 이슈 알림 발송"""
    print(f"[NOTIFICATION] Followed started (batch={batch_run_id[:8]}...)")

    try:
        with SessionLocal() as db:
            result = send_followed_notifications(db, batch_run_id)
            db.commit()
            print(f"[NOTIFICATION] Followed completed: {result.message}, sent={result.sent_count}")
            return result.to_dict()
    except Exception as e:
        print(f"[NOTIFICATION] Followed failed: {e}")
        return {"status": "failed", "error": str(e)}
