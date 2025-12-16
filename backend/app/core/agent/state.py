from typing import TypedDict, Annotated, Sequence
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """에이전트 상태 정의"""

    # 사용자 입력
    query: str

    # 메시지 히스토리
    messages: Annotated[Sequence[dict], add_messages]

    # 현재 단계
    current_step: str

    # 검색 결과
    search_results: list[dict]

    # 수집된 문서
    collected_documents: list[dict]

    # 분석 결과
    analysis: str

    # 신뢰도 점수
    credibility_scores: dict

    # 최종 리포트
    final_report: str

    # 반복 횟수 (무한 루프 방지)
    iteration_count: int

    # 에러 정보
    error: str | None