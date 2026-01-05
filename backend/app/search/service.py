"""검색 서비스 - 벡터 유사도 검색 + 텍스트 검색"""
from uuid import UUID
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text, or_

# 한국 시간대
KST = timezone(timedelta(hours=9))
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.issues.models import Issue, IssueArticle, IssueContent, IssueEmbedding
from app.core.agent.tools import EmbeddingProvider
from app.core.config import settings


class SearchService:
    """통합 검색 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_provider = EmbeddingProvider()

    async def search_all(
        self,
        query: str,
        limit: int = 20
    ) -> dict:
        """통합 검색 - 이슈, 기사, 콘텐츠 모두 검색

        Returns:
            {
                "issues": [...],
                "articles": [...],
                "contents": [...]
            }
        """
        issues = await self.search_issues(query, limit=limit // 2)
        articles = await self.search_articles(query, limit=limit // 2)
        contents = await self.search_contents(query, limit=limit // 2)

        return {
            "issues": issues,
            "articles": articles,
            "contents": contents,
            "total": len(issues) + len(articles) + len(contents)
        }

    async def search_issues(
        self,
        query: str,
        limit: int = 10
    ) -> list[dict]:
        """이슈 벡터 검색

        이슈 이름 임베딩과 쿼리 임베딩 유사도로 검색
        """
        query_embedding = self.embedding_provider.embed(query)

        # pgvector 유사도 검색
        stmt = text("""
            SELECT
                id,
                name,
                category,
                what_type,
                what_summary,
                first_seen_at,
                last_seen_at,
                status,
                1 - (name_embedding <=> CAST(:embedding AS vector)) as similarity
            FROM issues
            WHERE name_embedding IS NOT NULL
              AND status = 'active'
            ORDER BY name_embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """)

        result = await self.db.execute(
            stmt,
            {"embedding": str(query_embedding), "limit": limit}
        )
        rows = result.fetchall()

        return [
            {
                "id": str(row[0]),
                "name": row[1],
                "category": row[2],
                "what_type": row[3],
                "what_summary": row[4],
                "first_seen_at": row[5].isoformat() if row[5] else None,
                "last_seen_at": row[6].isoformat() if row[6] else None,
                "status": row[7],
                "similarity": float(row[8])
            }
            for row in rows
            if row[8] >= settings.SEARCH_MIN_SIMILARITY
        ]

    async def search_articles(
        self,
        query: str,
        limit: int = 10,
        days: int = 30
    ) -> list[dict]:
        """기사 검색 - 텍스트 기반

        제목과 설명에서 쿼리 포함 여부로 검색
        """
        cutoff = datetime.now(KST) - timedelta(days=days)

        # 텍스트 검색 (ILIKE)
        stmt = (
            select(IssueArticle)
            .options(selectinload(IssueArticle.issue))
            .where(
                IssueArticle.collected_at >= cutoff,
                or_(
                    IssueArticle.title.ilike(f"%{query}%"),
                    IssueArticle.description.ilike(f"%{query}%")
                )
            )
            .order_by(IssueArticle.collected_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        articles = result.scalars().all()

        return [
            {
                "id": str(a.id),
                "title": a.title,
                "description": a.description,
                "url": a.url,
                "press": a.press,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "collected_at": a.collected_at.isoformat() if a.collected_at else None,
                "issue_id": str(a.issue_id),
                "issue_name": a.issue.name if a.issue else None
            }
            for a in articles
        ]

    async def search_contents(
        self,
        query: str,
        limit: int = 10
    ) -> list[dict]:
        """콘텐츠 벡터 검색

        임베딩에서 가장 유사한 콘텐츠 검색
        """
        query_embedding = self.embedding_provider.embed(query)

        # 콘텐츠 임베딩에서 검색
        stmt = text("""
            SELECT
                ic.id,
                ic.issue_id,
                i.name as issue_name,
                ic.title,
                ic.content,
                ic.verified,
                ic.confidence_score,
                ic.created_at,
                1 - (ie.embedding <=> CAST(:embedding AS vector)) as similarity
            FROM issue_embeddings ie
            JOIN issues i ON i.id = ie.issue_id
            JOIN issue_contents ic ON ic.issue_id = ie.issue_id
            WHERE ie.embedding IS NOT NULL
            ORDER BY ie.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """)

        result = await self.db.execute(
            stmt,
            {"embedding": str(query_embedding), "limit": limit}
        )
        rows = result.fetchall()

        # 중복 제거 (같은 content_id가 여러 임베딩과 매칭될 수 있음)
        seen_ids = set()
        unique_results = []

        for row in rows:
            content_id = str(row[0])
            similarity = float(row[8])

            # 최소 유사도 필터
            if similarity < settings.SEARCH_MIN_SIMILARITY:
                continue

            if content_id in seen_ids:
                continue
            seen_ids.add(content_id)

            unique_results.append({
                "id": content_id,
                "issue_id": str(row[1]),
                "issue_name": row[2],
                "title": row[3],
                "content_preview": row[4][:200] + "..." if row[4] and len(row[4]) > 200 else row[4],
                "verified": row[5],
                "confidence_score": float(row[6]) if row[6] else 0.0,
                "created_at": row[7].isoformat() if row[7] else None,
                "similarity": similarity
            })

        return unique_results

    async def search_by_category(
        self,
        category: str,
        limit: int = 20
    ) -> list[dict]:
        """카테고리별 이슈 검색"""
        stmt = (
            select(Issue)
            .options(
                selectinload(Issue.articles),
                selectinload(Issue.contents)
            )
            .where(
                Issue.category == category,
                Issue.status == "active"
            )
            .order_by(Issue.last_seen_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        issues = result.scalars().all()

        return [
            {
                "id": str(issue.id),
                "name": issue.name,
                "category": issue.category,
                "what_type": issue.what_type,
                "what_summary": issue.what_summary,
                "first_seen_at": issue.first_seen_at.isoformat() if issue.first_seen_at else None,
                "last_seen_at": issue.last_seen_at.isoformat() if issue.last_seen_at else None,
                "article_count": len(issue.articles),
                "has_content": bool(issue.contents)
            }
            for issue in issues
        ]

    async def suggest(
        self,
        query: str,
        limit: int = 5
    ) -> list[str]:
        """검색어 자동완성 제안

        이슈 이름과 키워드에서 매칭되는 것 반환
        """
        # 이슈 이름에서 검색
        stmt = (
            select(Issue.name)
            .where(
                Issue.name.ilike(f"%{query}%"),
                Issue.status == "active"
            )
            .order_by(Issue.last_seen_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        issue_names = [row[0] for row in result.all()]

        return issue_names[:limit]
