"""유사한 이슈 병합 스크립트

임베딩 유사도가 높은 이슈를 하나로 병합

Usage:
    python scripts/merge_similar_issues.py [--dry-run] [--threshold 0.80]
"""
import asyncio
import argparse
from datetime import datetime

from sqlalchemy import select, text, update, delete

from app.core.database import create_async_session_factory

# 모든 모델 임포트 (relationship 의존성)
from app.issues.models import Issue, IssueDailySnapshot, IssueArticle, IssueFollow
from app.batch.models import BatchRun
from app.auth.models import User
from app.notifications.models import Notification
from app.settings.models import UserSettings
from app.insights.models import IssueInsight


async def merge_similar_issues(threshold: float = 0.80, dry_run: bool = False):
    """유사도가 높은 이슈 병합"""

    session_factory = create_async_session_factory()
    async with session_factory() as db:
        # 유사한 이슈 쌍 찾기
        query = text("""
            SELECT
                i1.id as id1,
                i2.id as id2,
                i1.name as name1,
                i2.name as name2,
                i1.created_at as created_at1,
                i2.created_at as created_at2,
                i1.total_snapshots as snapshots1,
                i2.total_snapshots as snapshots2,
                1 - (i1.name_embedding <=> i2.name_embedding) as similarity
            FROM issues i1
            JOIN issues i2 ON i1.id < i2.id
            WHERE i1.name_embedding IS NOT NULL
            AND i2.name_embedding IS NOT NULL
            AND i1.status = 'active'
            AND i2.status = 'active'
            AND 1 - (i1.name_embedding <=> i2.name_embedding) >= :threshold
            ORDER BY similarity DESC
        """)

        result = await db.execute(query, {"threshold": threshold})
        similar_pairs = result.all()

        print(f"유사도 {threshold} 이상 이슈 쌍: {len(similar_pairs)}개\n")

        if not similar_pairs:
            print("병합할 이슈가 없습니다.")
            return

        for row in similar_pairs:
            print(f"[{row.similarity:.3f}]")
            print(f"  1. {row.name1} (snapshots: {row.snapshots1}, created: {row.created_at1})")
            print(f"  2. {row.name2} (snapshots: {row.snapshots2}, created: {row.created_at2})")
            print()

        if dry_run:
            print("(dry-run 모드 - 실제 병합 없음)")
            return

        # 병합 실행 (더 오래된 이슈로 병합)
        merged_count = 0
        for row in similar_pairs:
            # 더 오래된 이슈를 main으로 선택
            if row.created_at1 <= row.created_at2:
                main_id, other_id = row.id1, row.id2
                main_name, other_name = row.name1, row.name2
            else:
                main_id, other_id = row.id2, row.id1
                main_name, other_name = row.name2, row.name1

            try:
                # 1. other의 스냅샷들을 main으로 이동
                await db.execute(
                    update(IssueDailySnapshot)
                    .where(IssueDailySnapshot.issue_id == other_id)
                    .values(issue_id=main_id)
                )

                # 2. other의 알림들을 main으로 이동
                await db.execute(
                    update(Notification)
                    .where(Notification.issue_id == other_id)
                    .values(issue_id=main_id)
                )

                # 3. other의 팔로우들을 main으로 이동 (중복 제외)
                # 이미 main을 팔로우 중인 유저는 제외
                result = await db.execute(
                    select(IssueFollow.user_id).where(IssueFollow.issue_id == main_id)
                )
                main_followers = set(r[0] for r in result.all())

                result = await db.execute(
                    select(IssueFollow).where(IssueFollow.issue_id == other_id)
                )
                other_follows = result.scalars().all()

                for follow in other_follows:
                    if follow.user_id not in main_followers:
                        follow.issue_id = main_id
                    else:
                        await db.delete(follow)

                # 4. main 이슈 업데이트 (total_snapshots, last_seen_at)
                main_issue = await db.get(Issue, main_id)
                other_issue = await db.get(Issue, other_id)

                if main_issue and other_issue:
                    main_issue.total_snapshots += other_issue.total_snapshots
                    if other_issue.last_seen_at > main_issue.last_seen_at:
                        main_issue.last_seen_at = other_issue.last_seen_at

                    # 5. other 이슈 삭제
                    await db.delete(other_issue)
                    await db.flush()

                    merged_count += 1
                    print(f"병합 완료: '{other_name}' → '{main_name}'")

            except Exception as e:
                print(f"병합 실패: {e}")

        await db.commit()
        print(f"\n완료! {merged_count}개 이슈 병합")


def main():
    parser = argparse.ArgumentParser(description="유사 이슈 병합")
    parser.add_argument("--dry-run", action="store_true", help="실제 병합 없이 확인만")
    parser.add_argument("--threshold", type=float, default=0.80, help="유사도 임계값 (기본: 0.80)")

    args = parser.parse_args()

    asyncio.run(merge_similar_issues(threshold=args.threshold, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
