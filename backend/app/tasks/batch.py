"""Celery 태스크 - 다이제스트 생성 및 이메일 발송"""
import asyncio
from datetime import datetime, timezone, timedelta

from app.core.celery_app import celery_app
from app.core.database import SessionLocal, create_async_session_factory

KST = timezone(timedelta(hours=9))


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

            # 어제의 다이제스트 데이터 조회 (async → sync로 변환)
            # IssueService는 async이므로 직접 쿼리 실행
            from app.issues.models import Issue, IssueDailySnapshot
            from collections import defaultdict

            yesterday_date = today_kst - timedelta(days=1)

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
                    "id": str(issue.id),
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
