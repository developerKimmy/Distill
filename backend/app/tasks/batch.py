"""Celery 태스크 - 다이제스트 생성 및 이메일 발송"""
import asyncio
import traceback
from datetime import datetime, timezone, timedelta

from app.core.celery_app import celery_app
from app.core.database import SessionLocal, create_async_session_factory
from app.core.config import settings
from app.common.utils import EmailService

KST = timezone(timedelta(hours=9))


def _send_error_alert(error_type: str, error_message: str, traceback_str: str = "", location: str = ""):
    """에러 알림 발송 헬퍼"""
    if not settings.ADMIN_EMAIL:
        return
    try:
        email_service = EmailService(
            gmail_user=settings.GMAIL_USER,
            gmail_app_password=settings.GMAIL_APP_PASSWORD
        )
        email_service.send_error_alert(
            recipient=settings.ADMIN_EMAIL,
            error_type=error_type,
            error_message=error_message,
            location=location or "Batch Task",
            traceback_str=traceback_str
        )
    except Exception as e:
        print(f"[BATCH] 에러 알림 발송 실패: {e}")


@celery_app.task(bind=True, name="app.tasks.batch.generate_daily_digest")
def generate_daily_digest(self):
    """데일리 다이제스트 생성 (매일 오후 11시)

    오늘 하루 이슈를 요약해서 다이제스트 생성
    """
    from app.content.digest import DigestGenerator

    print("[DIGEST] Daily digest generation started")

    async def _generate():
        AsyncSession = create_async_session_factory()

        async with AsyncSession() as db:
            try:
                generator = DigestGenerator(db)
                today = datetime.now(KST).date()

                digest = await generator.generate_daily_digest(today)

                if digest:
                    await db.commit()
                    print(f"[DIGEST] Digest generated for {today}")
                    return {
                        "status": "completed",
                        "date": str(today),
                    }
                else:
                    print(f"[DIGEST] No issues to generate digest for {today}")
                    return {
                        "status": "skipped",
                        "reason": "no_issues",
                        "date": str(today),
                    }
            except Exception as e:
                print(f"[DIGEST] Digest generation failed: {e}")
                _send_error_alert(
                    error_type="Digest Generation Error",
                    error_message=str(e),
                    traceback_str=traceback.format_exc(),
                    location="generate_daily_digest"
                )
                return {
                    "status": "failed",
                    "error": str(e),
                }

    result = asyncio.run(_generate())
    print(f"[DIGEST] Daily digest generation completed: {result}")
    return result


@celery_app.task(bind=True, name="app.tasks.batch.send_morning_digest")
def send_morning_digest(self):
    """아침 데일리 다이제스트 이메일 발송 (매일 오전 8시)

    어제 있었던 이슈를 요약해서 구독자에게 발송
    """
    from datetime import date, datetime, timedelta, timezone
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.auth.models import User
    from app.settings.models import UserSettings
    from app.issues.service import IssueService
    from app.common.utils import EmailService
    from app.core.config import settings

    print("[DIGEST] Morning digest started")

    # 어제 날짜 (KST 기준)
    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST)
    today_kst = now_kst.date()
    yesterday = (today_kst - timedelta(days=1)).isoformat()
    print(f"[DIGEST] KST now: {now_kst.isoformat()}, yesterday (target): {yesterday}")

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

            # 어제 수집된 기사를 이슈별로 그룹핑하여 조회
            from app.issues.models import Issue, IssueArticle, UNASSIGNED_ISSUE_ID
            from sqlalchemy import func
            from collections import defaultdict

            yesterday_date = today_kst - timedelta(days=1)

            # 어제 수집된 기사를 이슈별로 카운트 (UNASSIGNED 제외)
            stmt = (
                select(
                    Issue,
                    func.count(IssueArticle.id).label('article_count')
                )
                .join(IssueArticle, Issue.id == IssueArticle.issue_id)
                .where(
                    func.date(IssueArticle.collected_at) == yesterday_date,
                    Issue.id != UNASSIGNED_ISSUE_ID
                )
                .group_by(Issue.id)
                .order_by(func.count(IssueArticle.id).desc())
            )
            results = list(db.execute(stmt).all())

            if not results:
                print(f"[DIGEST] No articles for {yesterday}")
                return {"status": "skipped", "reason": "no_data"}

            # 카테고리별 그룹핑
            by_category = defaultdict(list)
            total_articles = 0
            new_issues_count = 0

            for issue, article_count in results:
                category = issue.category or "기타"
                is_new = issue.first_seen_at == yesterday_date

                if is_new:
                    new_issues_count += 1

                by_category[category].append({
                    "id": str(issue.id),
                    "name": issue.name,
                    "article_count": article_count,
                    "is_new": is_new,
                })
                total_articles += article_count

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
                        total_issues=len(results),
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
        _send_error_alert(
            error_type="Morning Digest Error",
            error_message=str(e),
            traceback_str=traceback.format_exc(),
            location="send_morning_digest"
        )
        return {"status": "failed", "error": str(e)}
