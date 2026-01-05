"""Resolve 노드 - Entity 해소 (제목 entity를 본문 기반으로 정규화)

검증 로직:
1. title_content_mismatch: 제목의 entity와 본문의 entity가 불일치
2. unresolved_alias: 축약형이 해소되지 않음
3. entity_not_in_content: 해소된 entity가 본문에 없음
"""
import json
import logging
import re
from openai import OpenAI

from app.monitoring.state import MonitoringState, NERData, ArticleData
from app.core.config import settings
from app.core.prompts import entity_resolution_prompt

logger = logging.getLogger(__name__)

# 배치 크기
BATCH_SIZE = 10

# 축약형 패턴 (해소되어야 하는 패턴)
ALIAS_PATTERNS = [
    r"^.{1,2}\s?(대통령|대표|장관|총리|위원장|회장|사장)$",  # X 대통령, X 대표
    r"^(현|전|前)\s?(대통령|대표|장관|총리)$",  # 현 대통령, 전 대표
]


class ResolveNode:
    """Entity 해소 노드"""

    def __init__(self):
        self.llm = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = "deepseek-chat"

    async def __call__(self, state: MonitoringState) -> dict:
        """Resolve 노드 실행

        1. 추출된 entity들을 본문과 함께 LLM에 전달
        2. 정규화된 entity 이름으로 업데이트
        """
        articles = state.get("collected_articles", [])
        entities = state.get("extracted_entities", [])
        errors = list(state.get("errors", []))

        if not entities:
            logger.info("해소할 entity 없음")
            return {
                "extracted_entities": entities,
                "errors": errors,
                "current_step": "resolved",
            }

        logger.info(f"=== Entity 해소 시작: {len(entities)}개 기사 ===")

        # entity를 article_idx로 인덱싱
        entity_map = {e["article_idx"]: e for e in entities}

        resolved_entities: list[NERData] = []

        # 배치 처리
        for batch_start in range(0, len(articles), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(articles))
            batch_articles = articles[batch_start:batch_end]

            try:
                batch_resolved = self._resolve_batch(
                    batch_articles, entity_map, batch_start
                )
                resolved_entities.extend(batch_resolved)
            except Exception as e:
                logger.error(f"배치 Entity 해소 실패: {e}")
                errors.append(f"Resolve batch {batch_start}: {str(e)}")
                # 실패 시 원본 유지 + 검증 실패 플래그
                for i, article in enumerate(batch_articles):
                    idx = batch_start + i
                    if idx in entity_map:
                        original = entity_map[idx]
                        original["validation_flags"] = ["resolve_failed"]
                        original["is_valid"] = False
                        resolved_entities.extend([original])

        logger.info(f"=== Entity 해소 완료 ===")

        return {
            "extracted_entities": resolved_entities,
            "errors": errors,
            "current_step": "resolved",
        }

    def _resolve_batch(
        self,
        articles: list[ArticleData],
        entity_map: dict[int, NERData],
        start_idx: int
    ) -> list[NERData]:
        """배치 Entity 해소"""

        # 프롬프트용 데이터 준비
        prompt_articles = []
        for i, article in enumerate(articles):
            idx = start_idx + i
            ner_data = entity_map.get(idx, {})

            prompt_articles.append({
                "idx": idx,
                "title": article["title"],
                "description": article.get("description"),
                "entities": ner_data.get("who", []),
            })

        prompt = entity_resolution_prompt(prompt_articles)

        # LLM 호출
        response = self.llm.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "뉴스 기사의 entity를 본문 기반으로 정규화하는 시스템입니다. JSON만 출력합니다."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        return self._apply_resolution(content, articles, entity_map, start_idx)

    def _apply_resolution(
        self,
        content: str,
        articles: list[ArticleData],
        entity_map: dict[int, NERData],
        start_idx: int
    ) -> list[NERData]:
        """해소 결과 적용 + 검증"""
        results = []
        batch_size = len(articles)

        try:
            data = json.loads(content)
            resolution_map = {}

            # idx별 해소 매핑 생성
            for item in data.get("results", []):
                idx = item.get("idx")
                if idx is None:
                    continue

                resolved = item.get("resolved", [])
                resolution_map[idx] = {
                    r["original"]: r for r in resolved if "original" in r
                }

            # 각 기사에 해소 결과 적용
            for i in range(batch_size):
                idx = start_idx + i
                article = articles[i]
                original_ner = entity_map.get(idx, {})
                resolutions = resolution_map.get(idx, {})

                validation_flags = []
                description = article.get("description", "") or ""

                # who 업데이트 + 검증
                updated_who = []
                for who in original_ner.get("who", []):
                    original_name = who.get("name", "")
                    resolution = resolutions.get(original_name)

                    if resolution:
                        canonical = resolution.get("canonical", original_name)

                        # 검증 1: 제목-본문 불일치 (글자 매칭)
                        if not self._has_common_chars(original_name, canonical):
                            validation_flags.append(
                                f"title_content_mismatch:{original_name}→{canonical}"
                            )
                            logger.warning(
                                f"[{idx}] 제목-본문 불일치: {original_name} → {canonical}"
                            )

                        # 검증 2: 해소된 entity가 본문에 있는지
                        if canonical not in description:
                            validation_flags.append(
                                f"entity_not_in_content:{canonical}"
                            )

                        updated_who.append({
                            "name": canonical,
                            "role": who.get("role", ""),
                            "type": resolution.get("type", who.get("type", "person")),
                            "original": original_name,
                        })
                    else:
                        # 검증 3: 축약형이 해소되지 않음
                        if self._is_alias_pattern(original_name):
                            validation_flags.append(
                                f"unresolved_alias:{original_name}"
                            )
                            logger.warning(
                                f"[{idx}] 미해소 축약형: {original_name}"
                            )

                        updated_who.append({
                            **who,
                            "original": original_name,
                        })

                # where도 해소
                updated_where = []
                for loc in original_ner.get("where", []):
                    resolution = resolutions.get(loc)
                    if resolution:
                        updated_where.append(resolution.get("canonical", loc))
                    else:
                        updated_where.append(loc)

                # 검증 결과 판단
                is_valid = len(validation_flags) == 0

                results.append(NERData(
                    article_idx=idx,
                    who=updated_who,
                    where=updated_where,
                    what_type=original_ner.get("what_type"),
                    what_summary=original_ner.get("what_summary"),
                    validation_flags=validation_flags,
                    is_valid=is_valid,
                ))

        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            # 파싱 실패 시 원본 유지 + 검증 실패
            for i in range(batch_size):
                idx = start_idx + i
                if idx in entity_map:
                    original = entity_map[idx]
                    results.append(NERData(
                        article_idx=idx,
                        who=original.get("who", []),
                        where=original.get("where", []),
                        what_type=original.get("what_type"),
                        what_summary=original.get("what_summary"),
                        validation_flags=["json_parse_failed"],
                        is_valid=False,
                    ))

        return results

    def _has_common_chars(self, original: str, resolved: str) -> bool:
        """원본과 해소된 이름에 공통 글자가 있는지 확인

        예: "윤 대통령" vs "윤석열" → "윤" 공통 → True
            "이 대통령" vs "윤석열" → 공통 없음 → False
        """
        # 직책/호칭 제거
        clean_original = re.sub(r"(대통령|대표|장관|총리|위원장|회장|사장|전|현|前)", "", original).strip()

        if not clean_original:
            return True  # 직책만 있는 경우는 패스

        # 첫 1-2글자가 겹치는지
        for char in clean_original[:2]:
            if char in resolved:
                return True

        return False

    def _is_alias_pattern(self, name: str) -> bool:
        """축약형 패턴인지 확인"""
        for pattern in ALIAS_PATTERNS:
            if re.match(pattern, name):
                return True
        return False


# 싱글톤 인스턴스
resolve_node = ResolveNode()
