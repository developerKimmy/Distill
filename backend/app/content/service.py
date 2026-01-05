"""콘텐츠 서비스 - 조회 및 검색

콘텐츠 생성은 app.content.generator에서 처리
"""
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.issues.models import Issue, IssueContent, IssueEmbedding
from app.core.agent.tools import EmbeddingProvider


class ContentService:
    """콘텐츠 조회 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_provider = EmbeddingProvider()

    async def get_content(self, issue_id: UUID) -> IssueContent | None:
        """이슈의 최신 콘텐츠 조회"""
        stmt = (
            select(IssueContent)
            .where(IssueContent.issue_id == issue_id)
            .order_by(IssueContent.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_content_by_id(self, content_id: UUID) -> IssueContent | None:
        """콘텐츠 ID로 조회"""
        stmt = (
            select(IssueContent)
            .options(selectinload(IssueContent.issue))
            .where(IssueContent.id == content_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_contents(self, issue_id: UUID) -> list[IssueContent]:
        """이슈의 모든 콘텐츠 조회"""
        stmt = (
            select(IssueContent)
            .where(IssueContent.issue_id == issue_id)
            .order_by(IssueContent.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_similar(self, query: str, limit: int = 10) -> list[dict]:
        """벡터 유사도 검색"""
        query_embedding = self.embedding_provider.embed(query)

        stmt = text("""
            SELECT
                id,
                issue_id,
                content_type,
                content,
                1 - (embedding <=> CAST(:embedding AS vector)) as similarity
            FROM issue_embeddings
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
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
                "issue_id": str(row[1]),
                "content_type": row[2],
                "content": row[3],
                "similarity": float(row[4])
            }
            for row in rows
        ]

    async def search_contents(
        self,
        query: str,
        limit: int = 10
    ) -> list[dict]:
        """콘텐츠 벡터 검색

        생성된 콘텐츠 중 쿼리와 가장 유사한 콘텐츠 반환
        """
        query_embedding = self.embedding_provider.embed(query)

        # 콘텐츠 임베딩에서 검색
        stmt = text("""
            SELECT
                ie.issue_id,
                i.name as issue_name,
                ic.id as content_id,
                ic.title,
                ic.content,
                1 - (ie.embedding <=> CAST(:embedding AS vector)) as similarity
            FROM issue_embeddings ie
            JOIN issues i ON i.id = ie.issue_id
            LEFT JOIN issue_contents ic ON ic.issue_id = ie.issue_id
            WHERE ie.embedding IS NOT NULL
              AND ie.content_type = 'summary'
            ORDER BY ie.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """)

        result = await self.db.execute(
            stmt,
            {"embedding": str(query_embedding), "limit": limit}
        )
        rows = result.fetchall()

        return [
            {
                "issue_id": str(row[0]),
                "issue_name": row[1],
                "content_id": str(row[2]) if row[2] else None,
                "title": row[3],
                "content": row[4][:200] if row[4] else None,
                "similarity": float(row[5])
            }
            for row in rows
        ]
