from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class Event:
    """감지된 이벤트"""
    type: str  # article_surge, sentiment_shift, followed_update, new_issue
    issue_id: UUID | None
    issue_name: str
    category: str | None
    importance: float  # 0.0 ~ 1.0
    message: str  # 알림 메시지
    data: dict = field(default_factory=dict)  # 추가 데이터


class BaseSensor(ABC):
    """이벤트 감지기 베이스 클래스"""

    @property
    @abstractmethod
    def sensor_type(self) -> str:
        """센서 타입 이름"""
        pass

    @abstractmethod
    async def detect(self, db: AsyncSession) -> list[Event]:
        """이벤트 감지 후 리스트 반환"""
        pass
