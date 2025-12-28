"""콘텐츠 갭 분석기 - 부족한 정보 식별"""
import json
from dataclasses import dataclass
from openai import OpenAI
from app.core.config import settings


@dataclass
class ContentGap:
    """부족한 정보 항목"""
    gap_type: str  # "fact", "context", "perspective", "data"
    description: str  # 무엇이 부족한지
    search_query: str  # 이걸 찾기 위한 검색어
    priority: str  # "high", "medium", "low"


@dataclass
class GapAnalysisResult:
    """갭 분석 결과"""
    gaps: list[ContentGap]
    key_claims: list[dict]  # 검증 필요한 핵심 주장들
    confidence: float  # 현재 정보의 충분도 (0~1)


class GapAnalyzer:
    """수집된 콘텐츠의 부족한 부분 분석"""

    def __init__(self):
        self.llm = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )

    def analyze(
        self,
        issue_name: str,
        articles: list[dict],
        keywords: list[str] | None = None
    ) -> GapAnalysisResult:
        """기사들을 분석해서 부족한 정보 식별

        Args:
            issue_name: 이슈 이름
            articles: [{"title": "", "description": "", "url": ""}, ...]
            keywords: 추출된 키워드들

        Returns:
            GapAnalysisResult: 부족한 정보와 검증 필요한 주장들
        """
        if not articles:
            return GapAnalysisResult(gaps=[], key_claims=[], confidence=0.0)

        articles_text = "\n\n".join([
            f"제목: {a.get('title', '')}\n내용: {a.get('description', '')}"
            for a in articles[:10]
        ])

        keywords_text = ", ".join(keywords) if keywords else "없음"

        prompt = f"""다음은 "{issue_name}" 이슈에 대해 수집된 기사들이다.

=== 수집된 기사 ===
{articles_text}

=== 추출된 키워드 ===
{keywords_text}

위 정보를 분석해서 다음을 JSON으로 답해라:

1. gaps: 부족한 정보 목록 (최대 5개)
   - gap_type: "fact" (팩트 검증 필요), "context" (배경 설명 필요), "perspective" (다른 관점 필요), "data" (수치/통계 필요)
   - description: 무엇이 부족한지 구체적으로
   - search_query: 이 정보를 찾기 위한 검색어
   - priority: "high", "medium", "low"

2. key_claims: 검증이 필요한 핵심 주장들 (최대 5개)
   - claim: 주장 내용
   - source: 어느 기사에서 나온 주장인지
   - verification_query: 이걸 검증하기 위한 검색어

3. confidence: 현재 정보의 충분도 (0.0 ~ 1.0)
   - 0.3 미만: 정보 매우 부족
   - 0.3~0.6: 기본 정보는 있으나 검증 필요
   - 0.6~0.8: 대체로 충분하나 보완 필요
   - 0.8 이상: 충분함

JSON만 답해라:
```json
{{
  "gaps": [...],
  "key_claims": [...],
  "confidence": 0.5
}}
```"""

        try:
            response = self.llm.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500
            )

            # 응답 검증
            if not response.choices:
                return GapAnalysisResult(gaps=[], key_claims=[], confidence=0.5)

            content = response.choices[0].message.content
            if not content:
                return GapAnalysisResult(gaps=[], key_claims=[], confidence=0.5)

            content = content.strip()

        except Exception as e:
            print(f"[GapAnalyzer] LLM 호출 실패: {e}")
            return GapAnalysisResult(gaps=[], key_claims=[], confidence=0.5)

        # JSON 파싱 (안전하게)
        try:
            # ```json ... ``` 형태면 추출
            if "```json" in content:
                parts = content.split("```json")
                if len(parts) > 1:
                    inner_parts = parts[1].split("```")
                    content = inner_parts[0] if inner_parts else content
            elif "```" in content:
                parts = content.split("```")
                if len(parts) > 1:
                    content = parts[1]

            data = json.loads(content)
        except (json.JSONDecodeError, IndexError) as e:
            print(f"[GapAnalyzer] JSON 파싱 실패: {e}")
            return GapAnalysisResult(gaps=[], key_claims=[], confidence=0.5)

        # 결과 변환
        gaps = [
            ContentGap(
                gap_type=g.get("gap_type", "context"),
                description=g.get("description", ""),
                search_query=g.get("search_query", ""),
                priority=g.get("priority", "medium")
            )
            for g in data.get("gaps", [])
        ]

        return GapAnalysisResult(
            gaps=gaps,
            key_claims=data.get("key_claims", []),
            confidence=data.get("confidence", 0.5)
        )

    def get_search_queries(self, result: GapAnalysisResult, max_queries: int = 5) -> list[str]:
        """갭 분석 결과에서 검색할 쿼리 추출 (우선순위순)

        Args:
            result: 갭 분석 결과
            max_queries: 최대 쿼리 수

        Returns:
            검색 쿼리 리스트 (우선순위순)
        """
        queries = []

        # 1. high priority gaps 먼저
        for gap in result.gaps:
            if gap.priority == "high" and gap.search_query:
                queries.append(gap.search_query)

        # 2. key claims verification queries
        for claim in result.key_claims:
            if claim.get("verification_query"):
                queries.append(claim["verification_query"])

        # 3. medium priority gaps
        for gap in result.gaps:
            if gap.priority == "medium" and gap.search_query:
                queries.append(gap.search_query)

        # 4. low priority gaps
        for gap in result.gaps:
            if gap.priority == "low" and gap.search_query:
                queries.append(gap.search_query)

        # 중복 제거하면서 순서 유지
        seen = set()
        unique = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique.append(q)

        return unique[:max_queries]
