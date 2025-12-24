import json
from dataclasses import dataclass
from openai import OpenAI
from app.core.config import settings


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

        prompt = f"""이슈: {issue_name}

아래는 이 이슈 관련 기사들입니다.

{articles_text}

---

이 기사들에서 블로그 콘텐츠 작성에 활용할 수 있는 구체적인 키워드를 추출해주세요.

규칙:
1. 구체적인 수치/금액이 포함된 키워드 (예: "과징금 1500억", "3370만건 유출")
2. 비교 대상 (예: "SKT 해킹 비교")
3. 후속 이슈 (예: "집단소송", "주가 전망")
4. 관련 인물/기관 (예: "개인정보보호위원회")
5. 5~10개 추출

JSON 형식으로 응답:
{{
  "keywords": ["키워드1", "키워드2", ...]
}}
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        return ExtractedKeywords(
            keywords=result.get("keywords", [])
        )