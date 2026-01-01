"""이슈/기사 중복 현황 확인 스크립트"""
import asyncio
from sqlalchemy import select, func, text

from app.core.database import create_async_session_factory

# 모든 모델 임포트 (relationship 의존성)
from app.issues.models import Issue, IssueDailySnapshot, IssueArticle
from app.batch.models import BatchRun
from app.auth.models import User
from app.notifications.models import Notification
from app.settings.models import UserSettings
from app.insights.models import IssueInsight


async def check_duplicates():
    session_factory = create_async_session_factory()
    async with session_factory() as db:
        # 1. 최근 이슈 목록
        print("=== 최근 이슈 목록 ===")
        result = await db.execute(
            select(Issue)
            .order_by(Issue.created_at.desc())
            .limit(30)
        )
        issues = result.scalars().all()

        for issue in issues:
            print(f"  {issue.name[:50]:<50} | {issue.created_at.date()} | {issue.status}")

        # 2. 이슈명 완전 중복
        print("\n=== 이슈명 완전 중복 ===")
        result = await db.execute(
            select(Issue.name, func.count(Issue.id).label('cnt'))
            .group_by(Issue.name)
            .having(func.count(Issue.id) > 1)
        )
        duplicates = result.all()
        if duplicates:
            for name, cnt in duplicates:
                print(f"  {name}: {cnt}개")
        else:
            print("  없음")

        # 3. 이슈명 임베딩 유사도 확인 (비슷한 이슈)
        print("\n=== 유사한 이슈명 (임베딩 유사도 > 0.8) ===")
        query = text("""
            SELECT
                i1.name as name1,
                i2.name as name2,
                1 - (i1.name_embedding <=> i2.name_embedding) as similarity
            FROM issues i1
            JOIN issues i2 ON i1.id < i2.id
            WHERE i1.name_embedding IS NOT NULL
            AND i2.name_embedding IS NOT NULL
            AND 1 - (i1.name_embedding <=> i2.name_embedding) > 0.8
            ORDER BY similarity DESC
            LIMIT 20
        """)
        result = await db.execute(query)
        similar_issues = result.all()
        if similar_issues:
            for name1, name2, sim in similar_issues:
                print(f"  [{sim:.2f}] {name1[:40]} <-> {name2[:40]}")
        else:
            print("  없음")

        # 4. 최근 기사 타이틀 유사도 확인
        print("\n=== 최근 기사 중 유사한 타이틀 (유사도 > 0.9) ===")
        query = text("""
            SELECT
                a1.title as title1,
                a2.title as title2,
                1 - (a1.title_embedding <=> a2.title_embedding) as similarity
            FROM issue_articles a1
            JOIN issue_articles a2 ON a1.id < a2.id
            WHERE a1.title_embedding IS NOT NULL
            AND a2.title_embedding IS NOT NULL
            AND a1.created_at > NOW() - INTERVAL '3 days'
            AND a2.created_at > NOW() - INTERVAL '3 days'
            AND 1 - (a1.title_embedding <=> a2.title_embedding) > 0.9
            ORDER BY similarity DESC
            LIMIT 20
        """)
        result = await db.execute(query)
        similar_articles = result.all()
        if similar_articles:
            for title1, title2, sim in similar_articles:
                print(f"  [{sim:.2f}]")
                print(f"    - {title1[:80]}")
                print(f"    - {title2[:80]}")
        else:
            print("  없음")

        # 5. 스냅샷당 기사 수 통계
        print("\n=== 최근 스냅샷별 기사 수 ===")
        query = text("""
            SELECT
                i.name,
                s.date,
                s.article_count,
                s.created_at
            FROM issue_daily_snapshots s
            JOIN issues i ON s.issue_id = i.id
            WHERE s.created_at > NOW() - INTERVAL '2 days'
            ORDER BY s.created_at DESC
            LIMIT 30
        """)
        result = await db.execute(query)
        snapshots = result.all()
        for name, date, count, created_at in snapshots:
            print(f"  {name[:40]:<40} | {date} | {count}개 기사 | {created_at}")


if __name__ == "__main__":
    asyncio.run(check_duplicates())
