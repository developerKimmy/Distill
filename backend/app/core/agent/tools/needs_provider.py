import json
from dataclasses import dataclass
from openai import OpenAI
from app.core.config import settings


@dataclass
class ExtractedNeeds:
    """추출된 니즈"""
    needs: list[str]
    content_directions: list[str]


class NeedsProvider:
    """LLM 기반 댓글 니즈 분석"""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = "deepseek-chat"

    def extract_needs(self, issue_name: str, comments: list[dict]) -> ExtractedNeeds:
        """댓글에서 니즈 추출

        Args:
            issue_name: 이슈명
            comments: [{"text": "...", "like_count": 123}, ...]
        """
        if not comments:
            return ExtractedNeeds(needs=[], content_directions=[])

        comments_text = "\n".join([
            f"[좋아요 {c['like_count']}] {c['text']}"
            for c in comments[:30]
        ])

        prompt = f"""이슈: {issue_name}

아래는 이 이슈 관련 YouTube 영상들의 인기 댓글입니다.

{comments_text}

---

이 댓글들을 분석해서:

1. **니즈**: 사람들이 궁금해하는 것, 알고 싶어하는 것 (5~10개)
   - 질문 형태로 정리 (예: "과징금 나오면 쿠팡 망하나?")

2. **콘텐츠 방향**: 이 니즈를 해결할 블로그 글 주제 (3~5개)
   - 구체적인 제목 형태로 (예: "쿠팡 해킹 과징금 전망과 주가 영향 분석")

JSON 형식으로 응답:
{{
  "needs": ["니즈1", "니즈2", ...],
  "content_directions": ["제목1", "제목2", ...]
}}
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        return ExtractedNeeds(
            needs=result.get("needs", []),
            content_directions=result.get("content_directions", [])
        )