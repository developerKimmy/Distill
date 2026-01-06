from fastapi import APIRouter, Depends, Header, HTTPException
from typing import Optional

from app.core.database import get_async_session
from app.core.config import settings
from app.batch.schemas import BatchTaskResponse
from app.auth.models import User
from app.auth.router import current_active_user


router = APIRouter(prefix="/batch", tags=["batch"])


def verify_cron_secret(x_cron_secret: Optional[str] = Header(None)):
    """Cron job 요청 검증 (선택적)"""
    cron_secret = getattr(settings, 'CRON_SECRET', None)
    if cron_secret and x_cron_secret != cron_secret:
        raise HTTPException(status_code=403, detail="Invalid cron secret")
    return True

@router.post("/agent/run", response_model=BatchTaskResponse)
async def run_agent_cron(
    _: bool = Depends(verify_cron_secret)
):
    """Agent 실행 (테스트/Cron용, 인증 불필요)"""
    from app.tasks.agent import run_agent_cycle

    task = run_agent_cycle.delay()

    return BatchTaskResponse(
        task_id=task.id,
        status="queued"
    )


@router.post("/digest/send")
async def send_digest_email(
    _: bool = Depends(verify_cron_secret)
):
    """Morning digest 이메일 발송 (테스트용)"""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, func
    from sqlalchemy.orm import Session
    from app.core.database import SessionLocal
    from app.auth.models import User
    from app.settings.models import UserSettings
    from app.issues.models import Issue, IssueArticle, UNASSIGNED_ISSUE_ID
    from app.common.utils import EmailService
    from collections import defaultdict

    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST)
    today_kst = now_kst.date()
    yesterday_date = today_kst - timedelta(days=1)
    yesterday = yesterday_date.isoformat()

    with SessionLocal() as db:
        # 어제 수집된 기사를 이슈별로 카운트
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
            return {"status": "skipped", "reason": "no_data", "date": yesterday}

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

        category_order = ["정치", "경제", "사회", "세계", "IT/과학", "연예", "스포츠", "기타"]
        categories = [
            {"category": cat, "issues": by_category[cat], "total_articles": sum(i["article_count"] for i in by_category[cat])}
            for cat in category_order if cat in by_category
        ]

        # ADMIN_EMAIL로 발송
        email_service = EmailService(
            gmail_user=settings.GMAIL_USER,
            gmail_app_password=settings.GMAIL_APP_PASSWORD
        )

        success = email_service.send_daily_digest(
            recipient=settings.ADMIN_EMAIL,
            digest_date=yesterday,
            total_issues=len(results),
            new_issues_count=new_issues_count,
            total_articles=total_articles,
            categories=categories
        )

        return {
            "status": "sent" if success else "failed",
            "recipient": settings.ADMIN_EMAIL,
            "date": yesterday,
            "total_issues": len(results),
            "total_articles": total_articles
        }
