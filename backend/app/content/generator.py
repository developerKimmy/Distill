"""콘텐츠 생성기 (RAG 기반)

이슈별 브리핑 생성:
1. 과거 기사/콘텐츠 검색 (RAG)
2. YouTube 댓글에서 니즈 추출
3. LLM으로 브리핑 생성
4. 검증
"""
import logging
from datetime import datetime, timezone, timedelta, date
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from openai import OpenAI

from app.core.config import settings
from app.core.prompts import content_generation_prompt
from app.core.agent.tools import EmbeddingProvider, YouTubeProvider, NeedsProvider
from app.core.agent.tools.tavily import TavilyProvider
from app.issues.models import (
    Issue, IssueArticle, IssueContent, IssueEmbedding, IssueInsight
)

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class ContentGenerator:
    """RAG 기반 콘텐츠 생성기"""

    # 검증이 필요한 최소 기사 수
    VERIFICATION_THRESHOLD = 5

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = "deepseek-chat"
        self.embedding_provider = EmbeddingProvider()
        self.youtube_provider = YouTubeProvider()
        self.needs_provider = NeedsProvider()

        # Tavily 검증용 (선택적)
        try:
            self.tavily_provider = TavilyProvider()
        except ValueError:
            self.tavily_provider = None
            logger.warning("Tavily API 키 없음 - 검증 기능 비활성화")

    async def generate_briefing(self, issue_id: UUID) -> IssueContent | None:
        """이슈 브리핑 생성

        Args:
            issue_id: 이슈 ID

        Returns:
            생성된 IssueContent 또는 None
        """
        logger.info(f"=== 브리핑 생성 시작: {issue_id} ===")

        # 1. 이슈 + 최근 기사 조회
        issue = await self._get_issue_with_articles(issue_id)
        if not issue:
            logger.error(f"이슈를 찾을 수 없음: {issue_id}")
            return None

        articles = issue.articles[:20]  # 최근 20개
        if not articles:
            logger.warning(f"기사가 없음: {issue.name}")
            return None

        logger.info(f"이슈: {issue.name}, 기사: {len(articles)}개")

        # 2. RAG - 과거 관련 콘텐츠 검색
        similar_contents = await self._search_similar_content(issue.name, limit=5)
        logger.info(f"RAG 검색: {len(similar_contents)}개 관련 콘텐츠")

        # 3. YouTube - 니즈 추출
        needs, content_directions = await self._extract_youtube_needs(issue.name)
        logger.info(f"YouTube 니즈: {len(needs)}개, 방향: {len(content_directions)}개")

        # 4. Tavily 검증 (기사 5개 미만인 경우)
        verification_result = None
        if len(articles) < self.VERIFICATION_THRESHOLD and self.tavily_provider:
            logger.info(f"기사 {len(articles)}개 - Tavily 검증 수행")
            verification_result = await self._verify_with_tavily(issue.name, articles)

        # 5. LLM으로 브리핑 생성
        briefing_text = await self._generate_with_llm(
            issue_name=issue.name,
            articles=articles,
            similar_contents=similar_contents,
            needs=needs,
            content_directions=content_directions
        )

        if not briefing_text:
            logger.error(f"브리핑 생성 실패: {issue.name}")
            return None

        # 6. 검증 결과 반영
        if verification_result and verification_result.get("unverified_claims"):
            briefing_text = self._append_verification_notice(
                briefing_text,
                verification_result["unverified_claims"]
            )

        # 7. 제목 추출
        title = self._extract_title(briefing_text, issue.name)

        # 8. 저장
        is_verified = not (verification_result and verification_result.get("unverified_claims"))
        content = IssueContent(
            issue_id=issue_id,
            title=title,
            content=briefing_text,
            verified=is_verified,
        )
        self.db.add(content)

        # 7. 니즈/방향 저장 (IssueInsight)
        if needs or content_directions:
            insight = IssueInsight(
                issue_id=issue_id,
                verified_angles={"needs": needs},
                content_directions={"directions": content_directions}
            )
            self.db.add(insight)

        await self.db.flush()

        logger.info(f"=== 브리핑 생성 완료: {title} ===")
        return content

    async def _get_issue_with_articles(self, issue_id: UUID) -> Issue | None:
        """이슈 + 기사 조회"""
        stmt = (
            select(Issue)
            .options(selectinload(Issue.articles))
            .where(Issue.id == issue_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _search_similar_content(
        self,
        query: str,
        limit: int = 5
    ) -> list[dict]:
        """RAG - 벡터 유사도로 관련 콘텐츠 검색"""
        try:
            query_embedding = self.embedding_provider.embed(query)

            stmt = text("""
                SELECT
                    ie.content,
                    ie.content_type,
                    1 - (ie.embedding <=> CAST(:embedding AS vector)) as similarity
                FROM issue_embeddings ie
                WHERE ie.embedding IS NOT NULL
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
                    "content": row[0],
                    "type": row[1],
                    "similarity": float(row[2])
                }
                for row in rows
                if row[2] >= 0.5  # 유사도 0.5 이상만
            ]
        except Exception as e:
            logger.error(f"RAG 검색 실패: {e}")
            return []

    async def _extract_youtube_needs(
        self,
        issue_name: str
    ) -> tuple[list[str], list[str]]:
        """YouTube 댓글에서 니즈 추출"""
        needs = []
        content_directions = []

        try:
            # 1. YouTube 검색
            videos = await self.youtube_provider.search_videos(
                issue_name, max_results=3
            )
            if not videos:
                return needs, content_directions

            # 2. 댓글 수집
            all_comments = []
            for video in videos:
                comments = await self.youtube_provider.get_top_comments(
                    video["video_id"], max_results=10
                )
                for comment in comments:
                    all_comments.append({
                        "text": comment["text"],
                        "like_count": comment["like_count"]
                    })

            if not all_comments:
                return needs, content_directions

            # 3. 니즈 추출 (LLM)
            extracted = self.needs_provider.extract_needs(issue_name, all_comments)
            needs = extracted.needs or []
            content_directions = extracted.content_directions or []

        except Exception as e:
            logger.warning(f"YouTube 니즈 추출 실패: {e}")

        return needs, content_directions

    async def _generate_with_llm(
        self,
        issue_name: str,
        articles: list[IssueArticle],
        similar_contents: list[dict],
        needs: list[str],
        content_directions: list[str]
    ) -> str | None:
        """LLM으로 브리핑 생성"""
        today_str = datetime.now(KST).strftime("%Y년 %m월 %d일")

        # 기사 텍스트 준비
        articles_text = "\n\n".join([
            f"제목: {a.title}\n내용: {a.description or '없음'}\n출처: {a.press or '알 수 없음'}"
            for a in articles[:10]
        ])

        # 과거 콘텐츠 텍스트
        similar_text = "\n".join([
            f"- {c['content'][:200]}..." if len(c['content']) > 200 else f"- {c['content']}"
            for c in similar_contents
        ]) if similar_contents else "없음"

        # 니즈/방향 텍스트
        needs_text = "\n".join([f"- {n}" for n in needs]) if needs else "없음"
        directions_text = "\n".join([f"- {d}" for d in content_directions]) if content_directions else "없음"

        # 키워드 추출 (기사 제목에서)
        keywords = self._extract_keywords_from_articles(articles)

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
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.3,
            )

            content = response.choices[0].message.content
            return content if content else None

        except Exception as e:
            logger.error(f"LLM 생성 실패: {e}")
            return None

    def _extract_keywords_from_articles(
        self,
        articles: list[IssueArticle]
    ) -> list[str]:
        """기사 제목에서 키워드 추출 (간단 버전)"""
        # 간단히 자주 등장하는 단어 추출
        from collections import Counter
        import re

        words = []
        for article in articles:
            # 제목에서 한글 단어 추출 (2글자 이상)
            matches = re.findall(r'[가-힣]{2,}', article.title)
            words.extend(matches)

        # 불용어 제거
        stopwords = {'대통령', '정부', '관련', '대해', '위해', '통해', '오늘', '내일', '어제'}
        words = [w for w in words if w not in stopwords]

        # 상위 10개
        counter = Counter(words)
        return [word for word, _ in counter.most_common(10)]

    def _extract_title(self, content: str, fallback: str) -> str:
        """콘텐츠에서 제목 추출"""
        import re
        # 마크다운 제목 패턴
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            title = match.group(1).strip()
            # "이슈명:", "이슈명 :" 등 접두사 제거
            title = re.sub(r"^이슈명\s*:\s*", "", title)
            return title
        return f"{fallback} 브리핑"

    async def generate_for_today(self) -> list[IssueContent]:
        """오늘 수집된 모든 이슈에 대해 브리핑 생성"""
        today = datetime.now(KST).date()

        # 오늘 기사가 있는 이슈들 조회
        stmt = (
            select(Issue)
            .join(IssueArticle)
            .where(
                IssueArticle.collected_at >= datetime.combine(today, datetime.min.time(), tzinfo=KST),
                Issue.status == "active"
            )
            .distinct()
        )
        result = await self.db.execute(stmt)
        issues = result.scalars().all()

        logger.info(f"오늘 브리핑 생성 대상: {len(issues)}개 이슈")

        contents = []
        for issue in issues:
            try:
                content = await self.generate_briefing(issue.id)
                if content:
                    contents.append(content)
            except Exception as e:
                logger.error(f"브리핑 생성 실패 [{issue.name}]: {e}")

        await self.db.commit()
        return contents

    # ========== Tavily 검증 ==========

    async def _verify_with_tavily(
        self,
        issue_name: str,
        articles: list[IssueArticle]
    ) -> dict:
        """Tavily로 기사 내용 검증

        Args:
            issue_name: 이슈명
            articles: 기사 목록

        Returns:
            {
                "verified_claims": [...],  # 검증된 내용
                "unverified_claims": [...]  # 미검증 내용
            }
        """
        try:
            # 1. Tavily 검색
            tavily_results = await self.tavily_provider.search(
                query=issue_name,
                max_results=5
            )

            if not tavily_results:
                logger.warning(f"Tavily 검색 결과 없음: {issue_name}")
                return {"verified_claims": [], "unverified_claims": []}

            # 2. 기사에서 주요 주장 추출
            claims = self._extract_claims_from_articles(articles)

            if not claims:
                return {"verified_claims": [], "unverified_claims": []}

            # 3. Tavily 결과 텍스트 준비
            tavily_text = "\n".join([
                f"- {r['title']}: {r['snippet']}"
                for r in tavily_results
            ])

            # 4. LLM으로 검증
            verification = self._verify_claims_with_llm(claims, tavily_text)

            logger.info(
                f"검증 완료: {len(verification['verified_claims'])}개 확인, "
                f"{len(verification['unverified_claims'])}개 미확인"
            )

            return verification

        except Exception as e:
            logger.error(f"Tavily 검증 실패: {e}")
            return {"verified_claims": [], "unverified_claims": []}

    def _extract_claims_from_articles(
        self,
        articles: list[IssueArticle]
    ) -> list[str]:
        """기사에서 주요 주장/팩트 추출"""
        prompt = f"""다음 뉴스 기사들에서 검증이 필요한 핵심 주장/팩트를 추출해주세요.

기사 목록:
{chr(10).join([f'- {a.title}' + (f': {a.description[:200]}' if a.description else '') for a in articles[:5]])}

규칙:
1. 구체적인 수치, 날짜, 사실관계 중심으로 추출
2. 5개 이내로 추출
3. 각 주장은 한 문장으로

JSON 형식으로 응답:
{{"claims": ["주장1", "주장2", ...]}}
"""

        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1,
            )

            import json
            result = response.choices[0].message.content
            # JSON 파싱
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]

            data = json.loads(result.strip())
            return data.get("claims", [])

        except Exception as e:
            logger.error(f"주장 추출 실패: {e}")
            return []

    def _verify_claims_with_llm(
        self,
        claims: list[str],
        tavily_text: str
    ) -> dict:
        """LLM으로 주장 검증"""
        prompt = f"""다음 주장들을 웹 검색 결과와 비교해서 검증해주세요.

## 검증할 주장
{chr(10).join([f'{i+1}. {c}' for i, c in enumerate(claims)])}

## 웹 검색 결과
{tavily_text}

## 검증 규칙
- 검색 결과에서 확인 가능한 내용 → verified
- 검색 결과에서 확인 불가 또는 다른 내용 → unverified

JSON 형식으로 응답:
{{
  "verified_claims": ["확인된 주장1", ...],
  "unverified_claims": ["미확인 주장1", ...]
}}
"""

        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1,
            )

            import json
            result = response.choices[0].message.content
            # JSON 파싱
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]

            data = json.loads(result.strip())
            return {
                "verified_claims": data.get("verified_claims", []),
                "unverified_claims": data.get("unverified_claims", [])
            }

        except Exception as e:
            logger.error(f"LLM 검증 실패: {e}")
            return {"verified_claims": [], "unverified_claims": []}

    def _append_verification_notice(
        self,
        content: str,
        unverified_claims: list[str]
    ) -> str:
        """콘텐츠에 미검증 안내 추가"""
        notice = "\n\n---\n\n## ⚠️ 미검증 내용\n\n"
        notice += "다음 내용은 추가 확인이 필요합니다:\n\n"
        for claim in unverified_claims:
            notice += f"- {claim}\n"
        notice += "\n*본 내용은 단일 출처에 기반하여 교차 검증이 완료되지 않았습니다.*"

        return content + notice
