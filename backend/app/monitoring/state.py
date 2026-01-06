"""모니터링 에이전트 State 정의

Pipeline: Collect → Extract → Match → Enrich → Detect → Notify
"""
from typing import TypedDict
from datetime import datetime


class ArticleData(TypedDict):
    """수집된 기사 데이터"""
    title: str
    url: str
    description: str | None
    press: str | None
    source: str  # google_news, naver, tavily
    published_at: datetime | None
    embedding: list[float] | None


class NERData(TypedDict):
    """NER 추출 결과"""
    article_idx: int
    who: list[dict]  # [{"name": "윤석열", "role": "대통령", "original": "윤 대통령"}]
    where: list[str]
    what_type: str | None
    what_summary: str | None
    # 검증 플래그
    validation_flags: list[str]  # ["title_content_mismatch", "unresolved_alias", ...]
    is_valid: bool  # 검증 통과 여부


class MatchResult(TypedDict):
    """이슈 매칭 결과"""
    article_idx: int
    issue_id: str
    issue_name: str
    is_new_issue: bool
    similarity: float


class EventData(TypedDict):
    """감지된 이벤트"""
    event_type: str  # article_surge, new_issue, followed_update
    issue_id: str | None
    issue_name: str | None
    data: dict


class MonitoringState(TypedDict):
    """모니터링 파이프라인 State"""

    # === 메타 정보 ===
    run_id: str
    started_at: datetime

    # === Collect 단계 ===
    collected_articles: list[ArticleData]

    # === Extract 단계 ===
    extracted_entities: list[NERData]

    # === Match 단계 ===
    matched_results: list[MatchResult]
    new_issues_created: list[dict]  # 새로 생성된 이슈 정보

    # === Agent 단계 ===
    agent_results: list[dict]  # IssueAgentState 결과들

    # === Enrich 단계 ===
    enriched_issues: list[str]  # 콘텐츠 생성된 issue_id 목록

    # === Detect 단계 ===
    detected_events: list[EventData]

    # === 공통 ===
    errors: list[str]
    current_step: str
