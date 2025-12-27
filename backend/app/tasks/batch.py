"""글로벌 배치 및 알림 태스크"""
import asyncio
import time
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, or_

from app.core.celery_app import celery_app

# 한국 시간대 (UTC+9)
KST = timezone(timedelta(hours=9))
from app.core.database import AsyncSessionLocal, SessionLocal
from app.core.config import settings
from app.batch.service import GlobalBatchService
from app.batch.models import BatchRun
from app.settings.models import UserSettings
from app.auth.models import User
from app.issues.models import Issue, IssueDailySnapshot, IssueFollow
from app.common.utils import EmailService
from app.auth.magic_link import get_magic_link_url


@celery_app.task(bind=True, name="app.tasks.batch.run_global_batch")
def run_global_batch(self, triggered_by: str = "scheduled"):
    """글로벌 배치 실행 (모든 유저 공유)"""
    print(f"[TASK] Global batch started, triggered_by: {triggered_by}")
    start = time.time()
    result = asyncio.run(_run_global_batch(triggered_by))
    duration = time.time() - start
    print(f"[TASK] Global batch completed in {duration:.2f}s")

    # 배치 완료 후 알림 태스크 트리거 (DB 충돌 방지를 위해 체이닝)
    if result.get("status") == "completed":
        batch_run_id = result.get("batch_run_id")
        batch_time = datetime.now(KST).strftime("%H:%M")
        print(f"[TASK] Triggering notifications for {batch_time}")
        # 카테고리 다이제스트 알림
        send_scheduled_notifications.delay(batch_time=batch_time)
        # 팔로우 이슈 알림 (별도 이메일)
        send_followed_issues_notifications.delay(batch_run_id=batch_run_id)

    return result


async def _run_global_batch(triggered_by: str):
    """비동기 글로벌 배치 실행"""
    async with AsyncSessionLocal() as db:
        service = GlobalBatchService(db)
        batch_run = await service.run(triggered_by=triggered_by)

        return {
            "batch_run_id": str(batch_run.id),
            "status": batch_run.status,
            "issues_created": batch_run.issues_created
        }


@celery_app.task(bind=True, name="app.tasks.batch.send_scheduled_notifications")
def send_scheduled_notifications(self, batch_time: str | None = None):
    """현재 시간에 알림 받을 유저들에게 이메일 발송 (동기 버전)

    Args:
        batch_time: 배치에서 트리거된 경우 배치 시작 시간 (HH:MM 형식)
    """
    print(f"[TASK] Checking scheduled notifications... (batch_time={batch_time})")
    result = _send_scheduled_notifications_sync(batch_time=batch_time)
    print(f"[TASK] Notification check completed: {result}")
    return result


def _send_scheduled_notifications_sync(batch_time: str | None = None):
    """동기 알림 발송 - Celery 태스크에서 안전하게 실행

    Args:
        batch_time: 배치에서 트리거된 경우 배치 시작 시간 (HH:MM 형식)
    """
    now = datetime.now(KST)

    if batch_time:
        # 배치에서 호출된 경우: 정확한 배치 시간만 체크
        check_times = [batch_time]
    else:
        # 정기 스케줄(:05/:35)에서 호출된 경우: 직전 :00/:30 시간도 함께 체크
        current_time = now.strftime("%H:%M")
        minute = now.minute

        check_times = [current_time]
        # :05에 실행되면 :00도 체크, :35에 실행되면 :30도 체크
        if minute == 5:
            check_times.append(f"{now.hour:02d}:00")
        elif minute == 35:
            check_times.append(f"{now.hour:02d}:30")

    print(f"[NOTIFICATION] Checking times: {check_times}")

    db = SessionLocal()
    try:
        # 최근 완료된 배치 조회
        batch_run = db.execute(
            select(BatchRun)
            .where(BatchRun.status == "completed")
            .order_by(BatchRun.completed_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if not batch_run:
            print("[NOTIFICATION] No completed batch found")
            return {"sent_count": 0, "message": "No completed batch found"}

        print(f"[NOTIFICATION] Found batch: {batch_run.id}, issues: {batch_run.issues_created}")

        # 체크 시간에 알림 받을 유저 조회
        time_conditions = [
            UserSettings.notification_times.contains(t) for t in check_times
        ]
        users = db.execute(
            select(User)
            .join(UserSettings)
            .where(
                UserSettings.email_notifications_enabled == True,
                or_(*time_conditions)
            )
        ).scalars().all()

        if not users:
            print(f"[NOTIFICATION] No users to notify at {check_times}")
            return {"sent_count": 0, "checked_at": check_times, "message": "No users to notify"}

        print(f"[NOTIFICATION] Found {len(users)} users to notify")

        # 이메일 발송
        sent_count = 0
        if settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD:
            email_service = EmailService(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)

            for user in users:
                try:
                    # 유저의 카테고리 설정 조회
                    user_settings = db.execute(
                        select(UserSettings).where(UserSettings.user_id == user.id)
                    ).scalar_one_or_none()

                    user_categories = []
                    if user_settings and user_settings.category_filter:
                        user_categories = user_settings.category_filter.split(",")

                    print(f"[NOTIFICATION] User {user.email} categories: {user_categories or 'all'}")

                    # 카테고리로 필터링된 이슈 조회
                    stmt = (
                        select(Issue, IssueDailySnapshot)
                        .join(IssueDailySnapshot, Issue.id == IssueDailySnapshot.issue_id)
                        .where(IssueDailySnapshot.batch_run_id == batch_run.id)
                    )

                    if user_categories:
                        stmt = stmt.where(Issue.category.in_(user_categories))

                    stmt = stmt.order_by(IssueDailySnapshot.article_count.desc())

                    rows = db.execute(stmt).all()
                    issues = []
                    for issue, snapshot in rows:
                        issues.append({
                            "name": issue.name,
                            "category": issue.category,
                            "summary": snapshot.summary,
                            "article_count": snapshot.article_count,
                        })

                    print(f"[NOTIFICATION] Found {len(issues)} category issues for {user.email}")

                    if issues:
                        # 매직 링크 생성
                        magic_url = get_magic_link_url(user.id)
                        print(f"[NOTIFICATION] Magic link for {user.email}: {magic_url[:50]}...")

                        success = email_service.send_issues_digest(
                            recipient=user.email,
                            issues=issues,
                            categories=user_categories if user_categories else None,
                            magic_link_url=magic_url,
                            batch_time=batch_run.completed_at
                        )
                        if success:
                            sent_count += 1
                            print(f"[NOTIFICATION] Sent to {user.email}")
                        else:
                            print(f"[NOTIFICATION] Failed to send to {user.email}")
                    else:
                        print(f"[NOTIFICATION] No issues to send for {user.email}")

                except Exception as e:
                    print(f"[NOTIFICATION] Error for {user.email}: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            print("[NOTIFICATION] Gmail settings not configured")

        return {
            "sent_count": sent_count,
            "checked_at": check_times,
            "batch_run_id": str(batch_run.id)
        }

    except Exception as e:
        print(f"[NOTIFICATION] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return {"sent_count": 0, "error": str(e)}

    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.batch.send_followed_issues_notifications")
def send_followed_issues_notifications(self, batch_run_id: str):
    """팔로우 이슈 업데이트 알림 발송 (배치 완료 후 호출)

    Args:
        batch_run_id: 배치 실행 ID
    """
    print(f"[TASK] Sending followed issues notifications for batch: {batch_run_id}")
    result = _send_followed_issues_notifications_sync(batch_run_id)
    print(f"[TASK] Followed issues notification completed: {result}")
    return result


def _send_followed_issues_notifications_sync(batch_run_id: str):
    """팔로우 이슈 알림 발송 (동기)"""
    from uuid import UUID

    db = SessionLocal()
    try:
        # 배치 조회
        batch_run = db.execute(
            select(BatchRun).where(BatchRun.id == UUID(batch_run_id))
        ).scalar_one_or_none()

        if not batch_run:
            print(f"[FOLLOWED] Batch not found: {batch_run_id}")
            return {"sent_count": 0, "message": "Batch not found"}

        # 이번 배치에서 업데이트된 이슈를 팔로우하는 유저들 조회
        # (팔로우 테이블 + 스냅샷 테이블 조인)
        stmt = (
            select(User, Issue, IssueDailySnapshot)
            .join(IssueFollow, User.id == IssueFollow.user_id)
            .join(Issue, IssueFollow.issue_id == Issue.id)
            .join(IssueDailySnapshot, Issue.id == IssueDailySnapshot.issue_id)
            .where(IssueDailySnapshot.batch_run_id == batch_run.id)
            .order_by(User.id, IssueDailySnapshot.article_count.desc())
        )

        rows = db.execute(stmt).all()

        if not rows:
            print("[FOLLOWED] No followed issues with updates")
            return {"sent_count": 0, "message": "No followed issues with updates"}

        # 유저별로 그룹핑
        user_issues: dict[str, list[dict]] = {}
        user_map: dict[str, User] = {}

        for user, issue, snapshot in rows:
            user_id = str(user.id)
            if user_id not in user_issues:
                user_issues[user_id] = []
                user_map[user_id] = user

            user_issues[user_id].append({
                "name": issue.name,
                "category": issue.category,
                "summary": snapshot.summary,
                "article_count": snapshot.article_count,
                "issue_id": str(issue.id),
            })

        print(f"[FOLLOWED] Found {len(user_issues)} users with followed issue updates")

        # 이메일 발송
        sent_count = 0
        if settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD:
            email_service = EmailService(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)

            for user_id, issues in user_issues.items():
                user = user_map[user_id]
                try:
                    magic_url = get_magic_link_url(user.id)

                    success = email_service.send_followed_issues_update(
                        recipient=user.email,
                        issues=issues,
                        magic_link_url=magic_url,
                        batch_time=batch_run.completed_at
                    )

                    if success:
                        sent_count += 1
                        print(f"[FOLLOWED] Sent to {user.email} ({len(issues)} issues)")
                    else:
                        print(f"[FOLLOWED] Failed to send to {user.email}")

                except Exception as e:
                    print(f"[FOLLOWED] Error for {user.email}: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            print("[FOLLOWED] Gmail settings not configured")

        return {
            "sent_count": sent_count,
            "total_users": len(user_issues),
            "batch_run_id": batch_run_id
        }

    except Exception as e:
        print(f"[FOLLOWED] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return {"sent_count": 0, "error": str(e)}

    finally:
        db.close()
