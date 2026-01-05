"""Enrich 노드 - 이슈 콘텐츠 생성 + 2차 검증

콘텐츠 생성 시 Entity 일관성 검증:
1. 생성된 콘텐츠에서 Entity 추출
2. 원본 기사의 Entity와 비교
3. 불일치 시 플래그 설정
"""
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from openai import OpenAI

from app.monitoring.state import MonitoringState, MatchResult
from app.core.config import settings
from app.core.prompts import content_generation_prompt, daily_digest_prompt
from app.issues.models import Issue, IssueArticle, IssueContent

logger = logging.getLogger(__name__)

# 한국 시간대
KST = timezone(timedelta(hours=9))


class EnrichNode:
    """콘텐츠 생성 노드"""

    def __init__(self):
        self.llm = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = "deepseek-chat"

    async def __call__(
        self,
        state: MonitoringState,
        db: AsyncSession
    ) -> dict:
        """Enrich 노드 실행

        1. 매칭된 이슈별로 기사 그룹화
        2. 각 이슈에 대해 콘텐츠 생성
        3. 2차 검증 (Entity 일관성)
        """
        matched_results = state.get("matched_results", [])
        articles = state.get("collected_articles", [])
        entities = state.get("extracted_entities", [])
        errors = list(state.get("errors", []))

        if not matched_results:
            logger.info("콘텐츠 생성할 매칭 결과 없음")
            return {
                "enriched_issues": [],
                "errors": errors,
                "current_step": "enriched",
            }

        logger.info(f"=== 콘텐츠 생성 시작 ===")

        # NER 데이터를 article_idx로 인덱싱
        ner_map = {e["article_idx"]: e for e in entities}

        # 이슈별로 기사 그룹화 (UNASSIGNED 제외)
        issue_articles = self._group_by_issue(matched_results, articles, ner_map)

        enriched_issues: list[str] = []

        for i, (issue_id, data) in enumerate(issue_articles.items()):
            try:
                content = await self._generate_issue_content(
                    issue_id=issue_id,
                    issue_name=data["issue_name"],
                    articles=data["articles"],
                    ner_list=data["ner_list"],
                    db=db
                )

                if content:
                    # 2차 검증
                    is_valid = self._validate_content(
                        content=content.content,
                        ner_list=data["ner_list"]
                    )

                    content.verified = is_valid
                    enriched_issues.append(issue_id)
                    logger.info(
                        f"콘텐츠 생성 완료: {data['issue_name']} "
                        f"(verified={is_valid})"
                    )

                # 매 5개마다 중간 커밋
                if (i + 1) % 5 == 0:
                    try:
                        await db.commit()
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"콘텐츠 생성 실패 [{issue_id}]: {e}")
                errors.append(f"Enrich [{issue_id}]: {str(e)}")
                # 에러 발생 시 롤백 후 계속
                try:
                    await db.rollback()
                except Exception:
                    pass
                continue

        try:
            await db.commit()
        except Exception:
            pass

        logger.info(f"=== 콘텐츠 생성 완료: {len(enriched_issues)}개 이슈 ===")

        return {
            "enriched_issues": enriched_issues,
            "errors": errors,
            "current_step": "enriched",
        }

    def _group_by_issue(
        self,
        matched_results: list[MatchResult],
        articles: list[dict],
        ner_map: dict
    ) -> dict:
        """이슈별로 기사 그룹화 (UNASSIGNED 제외)"""
        grouped = {}

        for result in matched_results:
            issue_id = result["issue_id"]
            issue_name = result["issue_name"]

            # UNASSIGNED 제외
            if issue_name == "UNASSIGNED":
                continue

            if issue_id not in grouped:
                grouped[issue_id] = {
                    "issue_name": issue_name,
                    "articles": [],
                    "ner_list": [],
                }

            idx = result["article_idx"]
            if idx < len(articles):
                grouped[issue_id]["articles"].append(articles[idx])

            if idx in ner_map:
                grouped[issue_id]["ner_list"].append(ner_map[idx])

        return grouped

    async def _generate_issue_content(
        self,
        issue_id: str,
        issue_name: str,
        articles: list[dict],
        ner_list: list[dict],
        db: AsyncSession
    ) -> IssueContent | None:
        """이슈 콘텐츠 생성"""

        if not articles:
            return None

        # 이슈 존재 여부 확인 (외래키 에러 방지)
        issue_exists = await db.execute(
            select(Issue.id).where(Issue.id == UUID(issue_id))
        )
        if not issue_exists.scalar_one_or_none():
            logger.warning(f"이슈가 존재하지 않음: {issue_id} ({issue_name})")
            return None

        today_str = datetime.now(KST).strftime("%Y년 %m월 %d일")

        # 기사 텍스트 준비
        articles_text = "\n\n".join([
            f"제목: {a['title']}\n내용: {a.get('description', '없음')}"
            for a in articles[:10]
        ])

        # NER에서 키워드 추출
        keywords = self._extract_keywords_from_ner(ner_list)

        # 핵심 관심사 생성 (NER 기반)
        needs_text = self._generate_needs_from_ner(ner_list)

        # 콘텐츠 생성
        prompt = content_generation_prompt(
            issue_name=issue_name,
            today_str=today_str,
            articles_text=articles_text,
            keywords=keywords,
            needs_text=needs_text,
            directions_text="없음",
            similar_text="없음"
        )

        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.3,
            )

            content_text = response.choices[0].message.content
            if not content_text:
                return None

            # 제목 생성 (콘텐츠 첫 줄에서 추출 또는 이슈명 사용)
            title = self._extract_title(content_text, issue_name)

            # DB 저장
            issue_content = IssueContent(
                issue_id=UUID(issue_id),
                title=title,
                content=content_text,
                verified=False,
            )
            db.add(issue_content)
            await db.flush()

            return issue_content

        except Exception as e:
            logger.error(f"LLM 콘텐츠 생성 실패: {e}")
            return None

    def _extract_keywords_from_ner(self, ner_list: list[dict]) -> list[str]:
        """NER 결과에서 키워드 추출"""
        keywords = set()

        for ner in ner_list:
            # who에서 이름 추출
            for who in ner.get("who", []):
                name = who.get("name")
                if name:
                    keywords.add(name)

            # where 추출
            for loc in ner.get("where", []):
                if loc:
                    keywords.add(loc)

            # what_type 추출
            what_type = ner.get("what_type")
            if what_type:
                type_keywords = {
                    "TRIAL": "재판",
                    "INVESTIGATION": "수사",
                    "LEGISLATION": "입법",
                    "POLICY": "정책",
                    "ACCIDENT": "사고",
                    "DIPLOMACY": "외교",
                    "ECONOMY": "경제",
                }
                keywords.add(type_keywords.get(what_type, what_type))

        return list(keywords)[:10]

    def _generate_needs_from_ner(self, ner_list: list[dict]) -> str:
        """NER 결과에서 핵심 관심사 생성"""
        if not ner_list:
            return "없음"

        # what_summary들 수집
        summaries = []
        for ner in ner_list:
            summary = ner.get("what_summary")
            if summary:
                summaries.append(f"- {summary}")

        if summaries:
            return "\n".join(summaries[:5])

        return "없음"

    def _extract_title(self, content: str, fallback: str) -> str:
        """콘텐츠에서 제목 추출"""
        # 마크다운 제목 패턴
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()

        return f"{fallback} 브리핑"

    def _validate_content(
        self,
        content: str,
        ner_list: list[dict]
    ) -> bool:
        """2차 검증: 생성된 콘텐츠의 Entity 일관성 검사

        검증 항목:
        1. 원본 기사의 주요 Entity가 콘텐츠에 등장하는지
        2. 콘텐츠에서 잘못된 Entity가 등장하지 않는지
        """
        if not ner_list:
            return True  # NER 데이터 없으면 패스

        # 원본 기사의 유효한 Entity 수집
        valid_entities = set()
        invalid_entities = set()

        for ner in ner_list:
            # 검증 플래그가 있는 Entity는 invalid로 분류
            validation_flags = ner.get("validation_flags", [])
            is_valid = ner.get("is_valid", True)

            for who in ner.get("who", []):
                name = who.get("name")
                original = who.get("original", name)

                if not is_valid:
                    # 1차 검증 실패한 Entity
                    if any("title_content_mismatch" in f for f in validation_flags):
                        # 제목-본문 불일치 → 원본만 invalid
                        invalid_entities.add(original)
                    else:
                        valid_entities.add(name)
                else:
                    valid_entities.add(name)

        # 콘텐츠에서 Entity 등장 확인
        content_lower = content.lower()

        # invalid Entity가 콘텐츠에 있으면 실패
        for inv in invalid_entities:
            if inv.lower() in content_lower:
                logger.warning(
                    f"[2차 검증 실패] 잘못된 Entity '{inv}'가 콘텐츠에 포함됨"
                )
                return False

        # valid Entity 중 최소 하나 이상 있어야 함
        found_valid = False
        for v in valid_entities:
            if v.lower() in content_lower:
                found_valid = True
                break

        if not found_valid and valid_entities:
            logger.warning(
                f"[2차 검증 실패] 유효한 Entity가 콘텐츠에 없음: {valid_entities}"
            )
            return False

        return True


# 싱글톤 인스턴스
enrich_node = EnrichNode()
