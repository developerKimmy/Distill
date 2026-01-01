"""이슈의 first_seen_at을 created_at 기준으로 수정하는 스크립트

문제: 흔한 키워드로 인해 오래된 기사가 연결되어 first_seen_at이 잘못 설정됨
해결: created_at 기준 7일 이내의 기사만 고려하여 first_seen_at 재계산

Usage:
    python scripts/fix_first_seen_at.py [--dry-run]
"""
import asyncio
import argparse
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import create_async_session_factory

# 모든 모델 임포트 (relationship 의존성)
from app.issues.models import IssueArticle, Issue, IssueDailySnapshot
from app.batch.models import BatchRun
from app.auth.models import User
from app.notifications.models import Notification
from app.settings.models import UserSettings
from app.insights.models import IssueInsight


async def fix_first_seen_at(dry_run: bool = False):
    """이슈의 first_seen_at을 created_at 기준으로 수정"""

    session_factory = create_async_session_factory()
    async with session_factory() as db:
        # 모든 이슈 조회
        result = await db.execute(select(Issue))
        issues = list(result.scalars().all())

        print(f"총 이슈 수: {len(issues)}개")

        fixed_count = 0
        for issue in issues:
            # 이슈 생성일 기준 7일 이내만 유효
            min_valid_date = issue.created_at - timedelta(days=7)

            # 유효한 기사 중 가장 오래된 published_at 찾기
            # IssueArticle -> IssueDailySnapshot -> Issue 관계를 따라감
            query = (
                select(func.min(IssueArticle.published_at))
                .join(IssueDailySnapshot, IssueArticle.snapshot_id == IssueDailySnapshot.id)
                .where(IssueDailySnapshot.issue_id == issue.id)
                .where(IssueArticle.published_at.isnot(None))
                .where(IssueArticle.published_at >= min_valid_date)
            )
            result = await db.execute(query)
            earliest_valid_date = result.scalar()

            # 유효한 기사가 없으면 created_at 사용
            if earliest_valid_date:
                new_first_seen_at = earliest_valid_date.date() if hasattr(earliest_valid_date, 'date') else earliest_valid_date
            else:
                new_first_seen_at = issue.created_at.date() if hasattr(issue.created_at, 'date') else issue.created_at

            # 변경이 필요한지 확인 (1일 이상 차이)
            if issue.first_seen_at and abs((issue.first_seen_at - new_first_seen_at).days) > 0:
                print(f"\n이슈: {issue.name[:40]}")
                print(f"  created_at: {issue.created_at}")
                print(f"  기존 first_seen_at: {issue.first_seen_at}")
                print(f"  새 first_seen_at: {new_first_seen_at}")

                if not dry_run:
                    issue.first_seen_at = new_first_seen_at
                    fixed_count += 1

        if not dry_run and fixed_count > 0:
            await db.commit()
            print(f"\n완료! {fixed_count}개 이슈 수정")
        elif dry_run:
            print(f"\n(dry-run 모드 - 실제 업데이트 없음)")
        else:
            print(f"\n수정이 필요한 이슈가 없습니다.")


def main():
    parser = argparse.ArgumentParser(description="이슈 first_seen_at 수정")
    parser.add_argument("--dry-run", action="store_true", help="실제 업데이트 없이 확인만")

    args = parser.parse_args()

    asyncio.run(fix_first_seen_at(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
