import time
from uuid import UUID
from datetime import date
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from openai import OpenAI

from app.issues.models import (
    IssueDailySnapshot, IssueEmbedding, IssueContent
)
from app.core.agent.tools import EmbeddingProvider, NaverNewsProvider, GapAnalyzer
from app.core.config import settings
from app.core.prompts import title_generation_prompt, content_generation_prompt


class ContentService:
    """콘텐츠 생성 서비스 (RAG 기반)"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_provider = EmbeddingProvider()
        self.news_provider = NaverNewsProvider()
        self.gap_analyzer = GapAnalyzer()
        self.llm = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )

    async def search_similar(self, query: str, limit: int = 10) -> list[dict]:
        """벡터 유사도 검색"""
        query_embedding = self.embedding_provider.embed(query)

        stmt = text("""
            SELECT 
                id,
                snapshot_id,
                content_type,
                content,
                1 - (embedding <=> :embedding) as similarity
            FROM issue_embeddings
            ORDER BY embedding <=> :embedding
            LIMIT :limit
        """)

        result = await self.db.execute(
            stmt,
            {"embedding": str(query_embedding), "limit": limit}
        )
        rows = result.fetchall()

        return [
            {
                "id": str(row.id),
                "snapshot_id": str(row.snapshot_id),
                "content_type": row.content_type,
                "content": row.content,
                "similarity": float(row.similarity)
            }
            for row in rows
        ]

    async def generate_content(self, snapshot_id: UUID) -> IssueContent | None:
        """스냅샷 기반 콘텐츠 생성 및 저장"""
        start = time.time()
        print(f"[CONTENT] generate_content started for snapshot: {snapshot_id}")

        # 1. 스냅샷 + 관련 데이터 조회
        print(f"[CONTENT]   Loading snapshot data...")
        stmt = (
            select(IssueDailySnapshot)
            .options(
                selectinload(IssueDailySnapshot.issue),
                selectinload(IssueDailySnapshot.articles),
                selectinload(IssueDailySnapshot.keywords),
                selectinload(IssueDailySnapshot.insights)
            )
            .where(IssueDailySnapshot.id == snapshot_id)
        )
        result = await self.db.execute(stmt)
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            return None

        issue_name = snapshot.issue.name

        # 2. 니즈/콘텐츠 방향 가져오기
        needs = []
        content_directions = []
        for insight in snapshot.insights:
            if insight.verified_angles:
                needs.extend(insight.verified_angles.get("needs", []))
            if insight.content_directions:
                content_directions.extend(insight.content_directions.get("directions", []))

        # 3. 기사/키워드 정리
        articles = [
            {"title": a.title, "description": a.description, "url": a.url}
            for a in snapshot.articles
        ]
        keywords = [k.keyword for k in snapshot.keywords]

        # 4. 벡터 검색으로 관련 콘텐츠 추가
        step_start = time.time()
        print(f"[CONTENT]   Vector search for related content...")
        if needs:
            query = f"{issue_name} {' '.join(needs[:3])}"
        else:
            query = issue_name

        similar_contents = await self.search_similar(query, limit=5)
        print(f"[CONTENT]   Vector search completed in {time.time() - step_start:.2f}s")

        # 5. 부족하면 네이버 검색으로 보충
        additional_articles = []
        if len(articles) < 3:
            step_start = time.time()
            print(f"[CONTENT]   Enriching with Naver search...")
            additional_articles = await self._enrich_with_search(issue_name, keywords)
            print(f"[CONTENT]   Naver search completed in {time.time() - step_start:.2f}s")

        # 6. LLM으로 콘텐츠 생성
        step_start = time.time()
        print(f"[CONTENT]   Generating content with LLM...")
        content_text = await self._generate_with_llm(
            issue_name=issue_name,
            snapshot_date=snapshot.date,
            articles=articles + additional_articles,
            keywords=keywords,
            needs=needs,
            content_directions=content_directions,
            similar_contents=similar_contents
        )
        print(f"[CONTENT]   LLM content generated in {time.time() - step_start:.2f}s")

        # 7. 제목 생성
        step_start = time.time()
        print(f"[CONTENT]   Generating title...")
        title = await self._generate_title(issue_name, needs, content_directions)
        print(f"[CONTENT]   Title generated in {time.time() - step_start:.2f}s")

        # 8. 저장
        issue_content = IssueContent(
            snapshot_id=snapshot_id,
            title=title,
            content=content_text
        )
        self.db.add(issue_content)
        await self.db.flush()  # Flush to get the ID for verify_content

        print(f"[CONTENT] generate_content completed in {time.time() - start:.2f}s")
        return issue_content

    async def get_content(self, snapshot_id: UUID) -> IssueContent | None:
        """생성된 콘텐츠 조회"""
        stmt = (
            select(IssueContent)
            .where(IssueContent.snapshot_id == snapshot_id)
            .order_by(IssueContent.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def verify_content(self, content_id: UUID) -> bool:
        """생성된 콘텐츠 팩트체크

        - 주요 수치/날짜/인물명 추출
        - 원본 기사와 대조
        - 신뢰도 점수 계산
        """
        # 콘텐츠 조회
        stmt = (
            select(IssueContent)
            .options(
                selectinload(IssueContent.snapshot).selectinload(IssueDailySnapshot.articles)
            )
            .where(IssueContent.id == content_id)
        )
        result = await self.db.execute(stmt)
        content = result.scalar_one_or_none()

        if not content:
            return False

        # 1. 원본 기사 데이터 준비
        articles_data = [
            {"title": a.title, "description": a.description or ""}
            for a in content.snapshot.articles
        ]
        issue_name = content.snapshot.issue.name if content.snapshot.issue else "Unknown"

        # 2. GapAnalyzer로 정보 충분도 분석
        gap_result = self.gap_analyzer.analyze(
            issue_name=issue_name,
            articles=articles_data,
            keywords=None
        )
        gap_confidence = gap_result.confidence  # 0.0 ~ 1.0

        # 3. 원본 기사 키워드 매칭 검증
        original_facts = set()
        for article in content.snapshot.articles:
            if article.title:
                original_facts.add(article.title.lower())
            if article.description:
                original_facts.add(article.description.lower())

        generated_content = content.content.lower()
        matched_facts = 0
        total_checks = 0

        for fact in original_facts:
            if len(fact) > 10:
                total_checks += 1
                key_parts = fact.split()[:5]
                if any(part in generated_content for part in key_parts if len(part) > 2):
                    matched_facts += 1

        keyword_score = matched_facts / total_checks if total_checks > 0 else 0.5

        # 4. 최종 신뢰도 = GapAnalyzer(60%) + 키워드매칭(40%)
        confidence_score = (gap_confidence * 0.6) + (keyword_score * 0.4)

        # 5. 검증 결과 저장 (60% 이상이면 verified)
        content.verified = confidence_score >= 0.6
        content.confidence_score = round(confidence_score, 2)

        print(f"[CONTENT] Fact-check: verified={content.verified}, "
              f"confidence={content.confidence_score:.2f} "
              f"(gap={gap_confidence:.2f}, keyword={keyword_score:.2f})")
        return content.verified

    async def _enrich_with_search(self, issue_name: str, keywords: list[str]) -> list[dict]:
        """네이버 검색으로 추가 기사 수집"""
        additional = []

        search_queries = [issue_name] + keywords[:2]
        for query in search_queries:
            results = self.news_provider.search_news(query, display=3)
            for article in results:
                additional.append({
                    "title": article.title,
                    "description": article.description,
                    "url": article.url
                })

        # 중복 제거
        seen_urls = set()
        unique = []
        for a in additional:
            if a["url"] not in seen_urls:
                seen_urls.add(a["url"])
                unique.append(a)

        return unique[:5]

    async def _generate_title(
        self,
        issue_name: str,
        needs: list[str],
        content_directions: list[str]
    ) -> str:
        """블로그 제목 생성"""
        if content_directions:
            return content_directions[0]

        if needs:
            try:
                prompt = title_generation_prompt(issue_name, needs)
                response = self.llm.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100
                )
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"[CONTENT] 제목 생성 실패: {e}")

        return f"{issue_name} 총정리"

    async def _generate_with_llm(
        self,
        issue_name: str,
        snapshot_date: date,
        articles: list[dict],
        keywords: list[str],
        needs: list[str],
        content_directions: list[str],
        similar_contents: list[dict]
    ) -> str:
        """LLM으로 블로그 콘텐츠 생성"""
        from datetime import datetime, timezone, timedelta
        KST = timezone(timedelta(hours=9))

        date_prefix = f"({snapshot_date.strftime('%m/%d')} 기준)"
        articles_text = "\n\n".join([
            f"{date_prefix} 제목: {a['title']}\n내용: {a.get('description', '없음')}\n출처: {a['url']}"
            for a in articles[:10]
        ])
        similar_text = "\n".join([f"- {c['content']}" for c in similar_contents])
        needs_text = "\n".join([f"- {n}" for n in needs]) if needs else "없음"
        directions_text = "\n".join([f"- {d}" for d in content_directions]) if content_directions else "없음"
        today_str = datetime.now(KST).strftime("%Y년 %m월 %d일")

        prompt = content_generation_prompt(
            issue_name=issue_name,
            today_str=today_str,
            articles_text=articles_text,
            keywords=keywords,
            needs_text=needs_text,
            directions_text=directions_text,
            similar_text=similar_text
        )

        try:
            response = self.llm.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000
            )

            if not response.choices or not response.choices[0].message.content:
                raise ValueError("LLM 응답이 비어있음")

            return response.choices[0].message.content

        except Exception as e:
            print(f"[CONTENT] LLM 콘텐츠 생성 실패: {e}")
            # 기본 콘텐츠 반환 (기사 요약)
            fallback = f"# {issue_name}\n\n"
            fallback += f"**{today_str} 기준 주요 내용**\n\n"
            for a in articles[:5]:
                fallback += f"- {a.get('title', '')}\n"
            return fallback