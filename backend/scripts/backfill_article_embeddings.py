"""기존 기사들에 title_embedding 백필하는 스크립트

Usage:
    python scripts/backfill_article_embeddings.py [--batch-size 100] [--dry-run]
"""
import asyncio
import argparse
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import create_async_session_factory
from app.core.agent.tools.embedding_provider import EmbeddingProvider

# 모든 모델 임포트 (relationship 의존성)
from app.issues.models import IssueArticle, Issue, IssueDailySnapshot
from app.batch.models import BatchRun
from app.auth.models import User
from app.notifications.models import Notification
from app.settings.models import UserSettings
from app.insights.models import IssueInsight


async def backfill_embeddings(batch_size: int = 100, dry_run: bool = False, days: int | None = None):
    """기존 기사들에 title_embedding 추가"""

    embedding_provider = EmbeddingProvider()

    session_factory = create_async_session_factory()
    async with session_factory() as db:
        # 임베딩이 없는 기사 수 확인
        count_query = select(func.count(IssueArticle.id)).where(IssueArticle.title_embedding.is_(None))
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            count_query = count_query.where(IssueArticle.created_at >= cutoff_date)

        result = await db.execute(count_query)
        total_count = result.scalar()

        print(f"임베딩이 없는 기사: {total_count}개")

        if dry_run:
            print("(dry-run 모드 - 실제 업데이트 없음)")
            return

        if total_count == 0:
            print("백필할 기사가 없습니다.")
            return

        # 배치로 처리
        processed = 0
        while processed < total_count:
            # 임베딩이 없는 기사 조회
            query = (
                select(IssueArticle)
                .where(IssueArticle.title_embedding.is_(None))
                .limit(batch_size)
            )
            if days:
                cutoff_date = datetime.now() - timedelta(days=days)
                query = query.where(IssueArticle.created_at >= cutoff_date)

            result = await db.execute(query)
            articles = list(result.scalars().all())

            if not articles:
                break

            # 제목 추출
            titles = [a.title for a in articles]

            # 배치 임베딩 생성
            try:
                embeddings = embedding_provider.embed_batch(titles)

                # 업데이트
                for article, embedding in zip(articles, embeddings):
                    article.title_embedding = embedding

                await db.commit()
                processed += len(articles)
                print(f"진행: {processed}/{total_count} ({processed/total_count*100:.1f}%)")

            except Exception as e:
                print(f"에러 발생: {e}")
                await db.rollback()
                break

        print(f"완료! {processed}개 기사 임베딩 생성")


def main():
    parser = argparse.ArgumentParser(description="기존 기사 title_embedding 백필")
    parser.add_argument("--batch-size", type=int, default=100, help="배치 크기 (기본: 100)")
    parser.add_argument("--dry-run", action="store_true", help="실제 업데이트 없이 개수만 확인")
    parser.add_argument("--days", type=int, default=None, help="최근 N일 기사만 처리 (기본: 전체)")

    args = parser.parse_args()

    asyncio.run(backfill_embeddings(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        days=args.days
    ))


if __name__ == "__main__":
    main()
