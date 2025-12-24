from openai import OpenAI

from app.core.config import settings


class EmbeddingProvider:
    """OpenAI 임베딩 API 사용"""

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPEN_AI_API_KEY)
        self.model = "text-embedding-3-small"
        self.dimensions = 384  # DB 스키마와 일치

    def embed(self, text: str) -> list[float]:
        """단일 텍스트 임베딩"""
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """배치 임베딩"""
        if not texts:
            return []

        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions
        )
        return [item.embedding for item in response.data]