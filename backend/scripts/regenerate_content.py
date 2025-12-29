"""콘텐츠 재생성 스크립트

기존 스냅샷들의 콘텐츠를 새 프롬프트로 재생성합니다.
"""
import asyncio
import sys
from datetime import date, timedelta
from uuid import UUID

sys.path.insert(0, "/home/kimmy/projects/distill/backend")

from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from app.core.database import create_async_session_factory
# Import all models to resolve relationships
from app.auth.models import User
from app.batch.models import BatchRun
from app.notifications.models import Notification
from app.settings.models import UserSettings
from app.insights.models import IssueInsight
from app.issues.models import IssueDailySnapshot, IssueContent, Issue, DailyDigest
from app.content.service import ContentService


async def regenerate_contents(target_date: date | None = None):
    """콘텐츠 재생성

    Args:
        target_date: 특정 날짜만 재생성. None이면 오늘
    """
    AsyncSession = create_async_session_factory()

    async with AsyncSession() as db:
        # 대상 스냅샷 조회
        if target_date is None:
            target_date = date.today()

        print(f"[REGENERATE] Target date: {target_date}")

        stmt = (
            select(IssueDailySnapshot)
            .options(selectinload(IssueDailySnapshot.issue))
            .where(IssueDailySnapshot.date == target_date)
        )
        result = await db.execute(stmt)
        snapshots = list(result.scalars().all())

        print(f"[REGENERATE] Found {len(snapshots)} snapshots")

        if not snapshots:
            print("[REGENERATE] No snapshots found")
            return

        # 기존 콘텐츠 삭제
        snapshot_ids = [s.id for s in snapshots]
        delete_stmt = delete(IssueContent).where(IssueContent.snapshot_id.in_(snapshot_ids))
        await db.execute(delete_stmt)
        await db.commit()
        print(f"[REGENERATE] Deleted existing contents")

        # 재생성
        content_service = ContentService(db)

        for i, snapshot in enumerate(snapshots, 1):
            issue_name = snapshot.issue.name if snapshot.issue else "Unknown"
            print(f"[REGENERATE] ({i}/{len(snapshots)}) Regenerating: {issue_name}")

            try:
                content = await content_service.generate_content(snapshot.id)
                if content:
                    await content_service.verify_content(content.id)
                    print(f"  ✓ Generated: {content.title[:50]}...")
                else:
                    print(f"  ✗ Failed to generate")
            except Exception as e:
                print(f"  ✗ Error: {e}")

        await db.commit()
        print(f"[REGENERATE] Done!")


async def generate_daily_digest(target_date: date | None = None):
    """일간 다이제스트 생성 및 저장"""
    from collections import defaultdict
    from openai import OpenAI
    from app.core.config import settings
    from app.core.prompts import daily_digest_prompt

    AsyncSession = create_async_session_factory()

    async with AsyncSession() as db:
        if target_date is None:
            target_date = date.today()

        print(f"[DIGEST] Generating digest for: {target_date}")

        # 기존 다이제스트가 있으면 삭제
        existing = await db.execute(
            select(DailyDigest).where(DailyDigest.date == target_date)
        )
        existing_digest = existing.scalar_one_or_none()
        if existing_digest:
            await db.delete(existing_digest)
            await db.commit()
            print("[DIGEST] Deleted existing digest")

        # 스냅샷 + 콘텐츠 조회
        stmt = (
            select(IssueDailySnapshot)
            .options(
                selectinload(IssueDailySnapshot.issue),
                selectinload(IssueDailySnapshot.contents)
            )
            .where(IssueDailySnapshot.date == target_date)
            .order_by(IssueDailySnapshot.article_count.desc())
        )
        result = await db.execute(stmt)
        snapshots = list(result.scalars().all())

        if not snapshots:
            print("[DIGEST] No snapshots found")
            return None

        # 카테고리별 그룹핑
        issues_by_category = defaultdict(list)
        for snapshot in snapshots:
            issue = snapshot.issue
            category = issue.category or "기타"

            # 콘텐츠 요약 (첫 번째 콘텐츠의 첫 100자)
            content_summary = ""
            if snapshot.contents:
                content = snapshot.contents[0].content
                # 한줄요약 섹션 추출 시도
                if "## 한줄 요약" in content:
                    try:
                        summary_start = content.index("## 한줄 요약") + len("## 한줄 요약")
                        summary_end = content.index("##", summary_start)
                        content_summary = content[summary_start:summary_end].strip()
                    except:
                        content_summary = content[:100]
                else:
                    content_summary = content[:100]

            issues_by_category[category].append({
                "name": issue.name,
                "summary": "",
                "content_summary": content_summary
            })

        # LLM으로 다이제스트 생성
        llm = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )

        date_str = target_date.strftime("%m월 %d일")
        prompt = daily_digest_prompt(date_str, dict(issues_by_category))

        print("[DIGEST] Calling LLM...")
        response = llm.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000
        )

        digest_content = response.choices[0].message.content
        print("[DIGEST] Generated!")

        # DB에 저장
        daily_digest = DailyDigest(
            date=target_date,
            summary=digest_content
        )
        db.add(daily_digest)
        await db.commit()
        print("[DIGEST] Saved to DB!")

        print("=" * 50)
        print(digest_content)
        print("=" * 50)

        return digest_content


async def get_all_dates_with_snapshots():
    """DB에 스냅샷이 있는 모든 날짜 조회"""
    from sqlalchemy import func

    AsyncSession = create_async_session_factory()
    async with AsyncSession() as db:
        stmt = select(IssueDailySnapshot.date).distinct().order_by(IssueDailySnapshot.date)
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]


async def regenerate_all_dates(content_only: bool = False, digest_only: bool = False):
    """모든 날짜의 콘텐츠 재생성"""
    dates = await get_all_dates_with_snapshots()
    print(f"[REGENERATE ALL] Found {len(dates)} dates: {dates}")

    for i, target_date in enumerate(dates, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(dates)}] Processing date: {target_date}")
        print('='*60)

        if not digest_only:
            await regenerate_contents(target_date)
        if not content_only:
            await generate_daily_digest(target_date)


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="콘텐츠 재생성 스크립트")
    parser.add_argument("--date", type=str, help="대상 날짜 (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help="모든 날짜 재생성")
    parser.add_argument("--digest-only", action="store_true", help="다이제스트만 생성")
    parser.add_argument("--content-only", action="store_true", help="콘텐츠만 재생성")

    args = parser.parse_args()

    if args.all:
        await regenerate_all_dates(
            content_only=args.content_only,
            digest_only=args.digest_only
        )
    else:
        target_date = None
        if args.date:
            target_date = date.fromisoformat(args.date)

        if args.digest_only:
            await generate_daily_digest(target_date)
        elif args.content_only:
            await regenerate_contents(target_date)
        else:
            # 둘 다 실행
            await regenerate_contents(target_date)
            await generate_daily_digest(target_date)


if __name__ == "__main__":
    asyncio.run(main())
