"""중복 기사 정리 스크립트

유사도 0.95 이상인 기사 중 오래된 것을 삭제

Usage:
    python scripts/cleanup_duplicate_articles.py [--dry-run] [--threshold 0.95]
"""
import asyncio
import argparse
from datetime import datetime, timedelta

from sqlalchemy import select, text, delete

from app.core.database import create_async_session_factory

# 모든 모델 임포트 (relationship 의존성)
from app.issues.models import IssueArticle, Issue, IssueDailySnapshot
from app.batch.models import BatchRun
from app.auth.models import User
from app.notifications.models import Notification
from app.settings.models import UserSettings
from app.insights.models import IssueInsight


async def cleanup_duplicates(threshold: float = 0.95, dry_run: bool = False):
    """유사도가 높은 중복 기사 정리"""

    session_factory = create_async_session_factory()
    async with session_factory() as db:
        # 유사도 높은 기사 쌍 찾기 (최근 7일)
        week_ago = datetime.now() - timedelta(days=7)

        query = text("""
            SELECT
                a1.id as id1,
                a2.id as id2,
                a1.title as title1,
                a2.title as title2,
                a1.created_at as created_at1,
                a2.created_at as created_at2,
                1 - (a1.title_embedding <=> a2.title_embedding) as similarity
            FROM issue_articles a1
            JOIN issue_articles a2 ON a1.id < a2.id
            WHERE a1.title_embedding IS NOT NULL
            AND a2.title_embedding IS NOT NULL
            AND a1.created_at > :week_ago
            AND a2.created_at > :week_ago
            AND 1 - (a1.title_embedding <=> a2.title_embedding) >= :threshold
            ORDER BY similarity DESC
        """)

        result = await db.execute(
            query,
            {"week_ago": week_ago, "threshold": threshold}
        )
        duplicates = result.all()

        print(f"유사도 {threshold} 이상 중복 쌍: {len(duplicates)}개")

        if not duplicates:
            print("삭제할 중복 기사가 없습니다.")
            return

        # 삭제할 ID 수집 (각 쌍에서 더 최근에 생성된 것 삭제)
        ids_to_delete = set()
        for row in duplicates:
            # 더 최근에 생성된 기사를 삭제
            if row.created_at1 > row.created_at2:
                ids_to_delete.add(row.id1)
            else:
                ids_to_delete.add(row.id2)

        print(f"삭제 대상: {len(ids_to_delete)}개 기사")

        if dry_run:
            print("\n(dry-run 모드 - 실제 삭제 없음)")
            print("\n삭제 예정 기사 샘플:")
            for row in duplicates[:10]:
                print(f"  [{row.similarity:.3f}]")
                print(f"    - {row.title1[:60]}")
                print(f"    - {row.title2[:60]}")
            return

        # 삭제 실행
        if ids_to_delete:
            delete_stmt = delete(IssueArticle).where(IssueArticle.id.in_(list(ids_to_delete)))
            result = await db.execute(delete_stmt)
            await db.commit()
            print(f"\n완료! {result.rowcount}개 기사 삭제")


def main():
    parser = argparse.ArgumentParser(description="중복 기사 정리")
    parser.add_argument("--dry-run", action="store_true", help="실제 삭제 없이 확인만")
    parser.add_argument("--threshold", type=float, default=0.95, help="유사도 임계값 (기본: 0.95)")

    args = parser.parse_args()

    asyncio.run(cleanup_duplicates(threshold=args.threshold, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
