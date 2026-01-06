"""Agent State 정의"""
from typing import TypedDict, Literal, Annotated
from datetime import datetime
from operator import add

from app.core.agent.tools.gap_analyzer import ContentGap


class ToolCall(TypedDict):
    """도구 호출 기록"""
    tool: str  # "tavily", "naver", "google_news"
    query: str
    reason: str
    results_count: int
    timestamp: str


class SupplementaryData(TypedDict):
    """추가 수집 데이터"""
    source: str  # "tavily", "youtube"
    query: str
    title: str
    url: str | None
    content: str


class IssueAgentState(TypedDict):
    """개별 이슈 Agent 상태 (LangGraph용)"""
    # 이슈 정보
    issue_id: str
    issue_name: str
    category: str | None

    # 수집된 데이터
    articles: list[dict]  # ArticleData 호환
    supplementary_data: Annotated[list[SupplementaryData], add]  # 추가 수집 (누적)

    # 분석 결과
    confidence: float
    gaps: list[ContentGap]
    key_claims: list[dict]

    # 다음 액션
    next_action: dict | None  # {"tool": "...", "query": "...", "reason": "..."}

    # 루프 제어
    iteration: int
    max_iterations: int
    status: Literal["analyzing", "deciding", "acting", "done"]

    # 기록
    actions_taken: Annotated[list[ToolCall], add]  # 누적
    errors: Annotated[list[str], add]  # 누적
