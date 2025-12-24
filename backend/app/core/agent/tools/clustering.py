import os
import json
from dataclasses import dataclass
from openai import OpenAI
from app.core.config import settings


@dataclass
class ClusteredIssue:
    """클러스터링된 이슈"""
    name: str
    summary: str
    category: str
    article_indices: list[int]
    issue_type: str = "ongoing"  # "ongoing" (진행형) or "concluded" (종결형)
    related_search_terms: list[str] = None  # 추가 검색어 (엔티티 기반)

    def __post_init__(self):
        if self.related_search_terms is None:
            self.related_search_terms = []


class ClusteringProvider:
    """LLM 기반 뉴스 클러스터링"""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = "deepseek-chat"

    def cluster_news(self, titles: list[str], existing_issues: list[str] = None, num_issues: int = 10) -> list[
        ClusteredIssue]:
        """뉴스 제목들을 이슈로 클러스터링"""
        titles_text = "\n".join([f"{i}. {t}" for i, t in enumerate(titles)])

        existing_text = ""
        if existing_issues:
            existing_text = f"""
    기존에 추적 중인 이슈 목록:
    {chr(10).join([f"- {name}" for name in existing_issues])}

    위 이슈에 해당하는 기사가 있으면 반드시 해당 이슈명을 그대로 사용하세요.
    새로운 이슈인 경우에만 새 이름을 만드세요.
    """

        prompt = f"""아래는 오늘 네이버 뉴스 랭킹에 오른 {len(titles)}개 기사 제목입니다.

    이 제목들을 분석해서 현재 가장 주목받는 이슈 {num_issues}개를 추출해주세요.
    {existing_text}
    규칙:
    1. 같은 사건/이슈를 다룬 기사들은 하나로 묶기
    2. 많이 언급될수록 중요한 이슈
    3. 각 이슈에 대해:
       - name: 이슈명 (검색 키워드로 쓸 수 있게 간결하게)
       - summary: 요약 (1-2문장)
       - article_indices: 관련 기사 인덱스 배열
       - category: 카테고리 (정치, 경제, 사회, 연예, 스포츠, IT/과학, 세계)
       - issue_type: "ongoing" (수사/재판/협상 등 진행 중) 또는 "concluded" (이미 종결된 사건)
       - related_search_terms: 후속 검색에 사용할 핵심 엔티티 (인물명, 기관명 등) 1~3개

    JSON 형식으로 응답:
    {{
      "issues": [
        {{
          "name": "이슈명",
          "summary": "요약",
          "article_indices": [0, 5, 12],
          "category": "카테고리",
          "issue_type": "ongoing",
          "related_search_terms": ["인물명", "기관명"]
        }}
      ]
    }}

    기사 제목:
    {titles_text}
    """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        issues = []
        for item in result.get("issues", []):
            issues.append(ClusteredIssue(
                name=item["name"],
                summary=item["summary"],
                category=item["category"],
                article_indices=item["article_indices"],
                issue_type=item.get("issue_type", "ongoing"),
                related_search_terms=item.get("related_search_terms", [])
            ))

        return issues