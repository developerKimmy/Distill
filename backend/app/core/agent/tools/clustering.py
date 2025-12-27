import json
from dataclasses import dataclass
from openai import OpenAI
from app.core.config import settings
from app.core.prompts import clustering_prompt


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
        prompt = clustering_prompt(titles, existing_issues, num_issues)

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