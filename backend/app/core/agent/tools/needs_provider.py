import json
from dataclasses import dataclass
from openai import OpenAI
from app.core.config import settings
from app.core.prompts import needs_extraction_prompt


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

        prompt = needs_extraction_prompt(issue_name, comments_text)

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