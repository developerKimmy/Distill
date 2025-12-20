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


class ClusteringProvider:
    """LLM 기반 뉴스 클러스터링"""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = "deepseek-chat"

    def cluster_news(self, titles: list[str], num_issues: int = 10) -> list[ClusteredIssue]:
        """뉴스 제목들을 이슈로 클러스터링"""
        titles_text = "\n".join([f"{i}. {t}" for i, t in enumerate(titles)])

        prompt = f"""아래는 오늘 네이버 뉴스 랭킹에 오른 {len(titles)}개 기사 제목입니다.

이 제목들을 분석해서 현재 가장 주목받는 이슈 {num_issues}개를 추출해주세요.

규칙:
1. 같은 사건/이슈를 다룬 기사들은 하나로 묶기
2. 많이 언급될수록 중요한 이슈
3. 각 이슈에 대해: 이슈명(검색 키워드로 쓸 수 있게 간결하게), 요약(1-2문장), 관련 기사 인덱스 배열, 카테고리

JSON 형식으로 응답:
{{
  "issues": [
    {{
      "name": "이슈명",
      "summary": "요약",
      "article_indices": [0, 5, 12],
      "category": "카테고리"
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
                article_indices=item["article_indices"]
            ))

        return issues