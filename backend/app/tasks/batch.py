"""배치 및 알림 Celery 태스크"""
import asyncio
import time
from datetime import datetime, timezone, timedelta

from app.core.celery_app import celery_app
from app.core.database import create_async_session_factory, SessionLocal
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
    """비동기 배치 실행

    Celery에서 asyncio.run()으로 호출되므로 매번 새 엔진 생성 필요
    """
    # 매번 새 세션 팩토리 생성 (이벤트 루프 충돌 방지)
    AsyncSession = create_async_session_factory()

    async with AsyncSession() as db:
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


@celery_app.task(bind=True, name="app.tasks.batch.send_morning_digest")
def send_morning_digest(self):
    """아침 데일리 다이제스트 이메일 발송 (매일 오전 8시)

    어제 있었던 이슈를 요약해서 구독자에게 발송
    """
    from datetime import date, timedelta
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.auth.models import User
    from app.settings.models import UserSettings
    from app.issues.service import IssueService
    from app.common.utils import EmailService
    from app.core.config import settings

    print("[DIGEST] Morning digest started")

    # 어제 날짜
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    try:
        with SessionLocal() as db:
            # 이메일 알림 활성화된 사용자 조회
            query = (
                select(User)
                .join(UserSettings, User.id == UserSettings.user_id)
                .options(selectinload(User.settings))
                .where(
                    User.is_active == True,
                    UserSettings.email_notifications_enabled == True
                )
            )
            result = db.execute(query)
            users = list(result.scalars().all())

            if not users:
                print("[DIGEST] No users with email notifications enabled")
                return {"status": "skipped", "reason": "no_users"}

            # 어제의 다이제스트 데이터 조회 (async → sync로 변환)
            # IssueService는 async이므로 직접 쿼리 실행
            from app.issues.models import Issue, IssueDailySnapshot
            from collections import defaultdict

            yesterday_date = date.today() - timedelta(days=1)

            stmt = (
                select(IssueDailySnapshot)
                .join(Issue)
                .options(selectinload(IssueDailySnapshot.issue))
                .where(IssueDailySnapshot.date == yesterday_date)
                .order_by(IssueDailySnapshot.article_count.desc())
            )
            snapshots = list(db.execute(stmt).scalars().all())

            if not snapshots:
                print(f"[DIGEST] No snapshots for {yesterday}")
                return {"status": "skipped", "reason": "no_data"}

            # 카테고리별 그룹핑
            by_category = defaultdict(list)
            total_articles = 0
            new_issues_count = 0

            for snapshot in snapshots:
                issue = snapshot.issue
                category = issue.category or "기타"
                is_new = issue.first_seen_at == yesterday_date

                if is_new:
                    new_issues_count += 1

                by_category[category].append({
                    "name": issue.name,
                    "article_count": snapshot.article_count,
                    "is_new": is_new,
                })
                total_articles += snapshot.article_count

            # 카테고리 데이터 구조화
            category_order = ["정치", "경제", "사회", "세계", "IT/과학", "연예", "스포츠", "기타"]
            categories = []
            for cat in category_order:
                if cat in by_category:
                    categories.append({
                        "category": cat,
                        "issues": by_category[cat],
                        "total_articles": sum(i["article_count"] for i in by_category[cat])
                    })

            # 이메일 발송
            email_service = None
            if settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD:
                email_service = EmailService(
                    gmail_user=settings.GMAIL_USER,
                    gmail_app_password=settings.GMAIL_APP_PASSWORD
                )

            if not email_service:
                print("[DIGEST] Email service not configured")
                return {"status": "skipped", "reason": "no_email_config"}

            sent_count = 0
            for user in users:
                try:
                    success = email_service.send_daily_digest(
                        recipient=user.email,
                        digest_date=yesterday,
                        total_issues=len(snapshots),
                        new_issues_count=new_issues_count,
                        total_articles=total_articles,
                        categories=categories
                    )
                    if success:
                        sent_count += 1
                except Exception as e:
                    print(f"[DIGEST] Failed to send to {user.email}: {e}")

            print(f"[DIGEST] Morning digest completed: {sent_count}/{len(users)} emails sent")
            return {
                "status": "completed",
                "sent_count": sent_count,
                "total_users": len(users),
                "digest_date": yesterday
            }

    except Exception as e:
        print(f"[DIGEST] Morning digest failed: {e}")
        return {"status": "failed", "error": str(e)}
