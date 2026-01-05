"""Extract 노드 - NER (Named Entity Recognition) 추출"""
import json
import logging
from openai import OpenAI

from app.monitoring.state import MonitoringState, NERData, ArticleData
from app.core.config import settings
from app.core.prompts import ner_extraction_prompt

logger = logging.getLogger(__name__)

# 배치 크기 (한 번에 처리할 기사 수)
BATCH_SIZE = 10


class ExtractNode:
    """NER 추출 노드 (DeepSeek LLM 사용)"""

    def __init__(self):
        self.llm = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = "deepseek-chat"

    async def __call__(self, state: MonitoringState) -> dict:
        """Extract 노드 실행

        1. 수집된 기사들을 배치로 나눔
        2. 각 배치에 대해 NER 추출
        3. 결과를 state에 저장
        """
        articles = state.get("collected_articles", [])
        errors = list(state.get("errors", []))
        extracted: list[NERData] = []

        if not articles:
            logger.info("추출할 기사 없음")
            return {
                "extracted_entities": [],
                "errors": errors,
                "current_step": "extracted",
            }

        logger.info(f"=== NER 추출 시작: {len(articles)}개 기사 ===")

        # 배치 처리
        for batch_start in range(0, len(articles), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(articles))
            batch = articles[batch_start:batch_end]

            logger.info(f"배치 처리 중: {batch_start + 1}~{batch_end}")

            try:
                batch_results = self._extract_batch(batch, batch_start)
                extracted.extend(batch_results)
            except Exception as e:
                logger.error(f"배치 NER 추출 실패: {e}")
                errors.append(f"Extract batch {batch_start}: {str(e)}")

        logger.info(f"=== NER 추출 완료: {len(extracted)}개 결과 ===")

        return {
            "extracted_entities": extracted,
            "errors": errors,
            "current_step": "extracted",
        }

    def _extract_batch(
        self,
        articles: list[ArticleData],
        start_idx: int
    ) -> list[NERData]:
        """배치 NER 추출"""
        # 프롬프트용 데이터 준비
        prompt_articles = [
            {
                "idx": start_idx + i,
                "title": article["title"],
                "description": article.get("description"),
            }
            for i, article in enumerate(articles)
        ]

        prompt = ner_extraction_prompt(prompt_articles)

        # LLM 호출
        response = self.llm.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "뉴스 기사에서 핵심 정보를 추출하는 NER 시스템입니다. JSON만 출력합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # 일관성 있는 추출을 위해 낮은 temperature
            response_format={"type": "json_object"}
        )

        # 응답 파싱
        content = response.choices[0].message.content
        result = self._parse_response(content, start_idx, len(articles))

        return result

    def _parse_response(
        self,
        content: str,
        start_idx: int,
        batch_size: int
    ) -> list[NERData]:
        """LLM 응답 파싱"""
        results = []

        try:
            data = json.loads(content)
            items = data.get("results", [])

            # idx별로 정리
            idx_map = {item["idx"]: item for item in items if "idx" in item}

            # 각 기사에 대해 결과 생성
            for i in range(batch_size):
                article_idx = start_idx + i
                item = idx_map.get(article_idx, {})

                ner_data = NERData(
                    article_idx=article_idx,
                    who=item.get("who", []),
                    where=item.get("where", []),
                    what_type=item.get("what_type"),
                    what_summary=item.get("what_summary"),
                )
                results.append(ner_data)

        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            logger.debug(f"응답 내용: {content[:500]}")

            # 파싱 실패 시 빈 결과 생성
            for i in range(batch_size):
                results.append(NERData(
                    article_idx=start_idx + i,
                    who=[],
                    where=[],
                    what_type=None,
                    what_summary=None,
                ))

        return results


# 싱글톤 인스턴스
extract_node = ExtractNode()
