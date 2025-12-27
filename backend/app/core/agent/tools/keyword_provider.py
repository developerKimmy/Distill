import json
from dataclasses import dataclass
from openai import OpenAI
from app.core.config import settings
from app.core.prompts import keyword_extraction_prompt


@dataclass
class ExtractedKeywords:
    """추출된 키워드"""
    keywords: list[str]


class KeywordProvider:
    """LLM 기반 키워드 추출"""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = "deepseek-chat"

    def extract_keywords(self, issue_name: str, articles: list[dict]) -> ExtractedKeywords:
        """기사 description에서 콘텐츠용 키워드 추출

        Args:
            issue_name: 이슈명 (예: "쿠팡 해킹")
            articles: [{"title": "...", "description": "..."}, ...]
        """
        articles_text = "\n\n".join([
            f"제목: {a['title']}\n내용: {a['description']}"
            for a in articles if a.get('description')
        ])

        prompt = keyword_extraction_prompt(issue_name, articles_text)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        return ExtractedKeywords(
            keywords=result.get("keywords", [])
        )