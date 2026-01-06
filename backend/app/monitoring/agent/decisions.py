"""Agent 판단 로직 - 다음 액션 결정"""
import logging
from app.core.agent.tools.gap_analyzer import ContentGap
from app.core.config import settings

logger = logging.getLogger(__name__)


def decide_next_action(
    issue_name: str,
    articles_count: int,
    confidence: float,
    gaps: list[ContentGap],
    actions_taken: list[dict]
) -> dict | None:
    """다음 액션 결정

    Args:
        issue_name: 이슈명
        articles_count: 현재 기사 수
        confidence: 정보 충분도 (0~1)
        gaps: 부족한 정보 리스트
        actions_taken: 이미 수행한 액션들

    Returns:
        {"tool": "...", "query": "...", "reason": "..."} 또는 None (종료)
    """
    # Rule 1: 충분히 높은 confidence면 종료
    if confidence >= settings.AGENT_CONFIDENCE_THRESHOLD:
        logger.info(f"[Decision] confidence {confidence:.2f} >= {settings.AGENT_CONFIDENCE_THRESHOLD} → 종료")
        return None

    # Rule 2: 기사가 너무 적으면 무조건 추가 수집
    if articles_count < 2:
        return {
            "tool": "naver",
            "query": issue_name,
            "reason": f"기사 수 부족 ({articles_count}개)"
        }

    # 이미 시도한 쿼리 추출
    tried_queries = {a.get("query", "").lower() for a in actions_taken}
    tried_tools = {a.get("tool") for a in actions_taken}

    # Rule 3: High priority gaps 처리
    for gap in gaps:
        if gap.priority == "high" and gap.search_query.lower() not in tried_queries:
            tool = _select_tool_for_gap(gap, tried_tools)
            return {
                "tool": tool,
                "query": gap.search_query,
                "reason": f"[high] {gap.description[:50]}"
            }

    # Rule 4: Medium priority gaps
    for gap in gaps:
        if gap.priority == "medium" and gap.search_query.lower() not in tried_queries:
            tool = _select_tool_for_gap(gap, tried_tools)
            return {
                "tool": tool,
                "query": gap.search_query,
                "reason": f"[medium] {gap.description[:50]}"
            }

    # Rule 5: 기본 이슈명으로 검색 (아직 안 했으면)
    if issue_name.lower() not in tried_queries:
        # 아직 tavily 안 썼으면 tavily, 아니면 naver
        if "tavily" not in tried_tools:
            return {
                "tool": "tavily",
                "query": issue_name,
                "reason": "기본 이슈명 웹 검색"
            }
        elif "naver" not in tried_tools:
            return {
                "tool": "naver",
                "query": issue_name,
                "reason": "기본 이슈명 뉴스 검색"
            }

    # 더 이상 할 게 없음
    logger.info(f"[Decision] 추가 액션 없음 → 종료")
    return None


def _select_tool_for_gap(gap: ContentGap, tried_tools: set[str]) -> str:
    """Gap 유형에 따른 도구 선택

    Args:
        gap: ContentGap
        tried_tools: 이미 사용한 도구들

    Returns:
        도구 이름
    """
    # Gap 타입별 우선 도구
    tool_priority = {
        "fact": ["tavily", "naver", "google_news"],      # 팩트 검증 → 웹 검색
        "context": ["naver", "google_news", "tavily"],   # 배경 정보 → 뉴스
        "perspective": ["naver", "tavily"],              # 관점 → 뉴스
        "data": ["tavily", "naver"],                     # 통계 → 웹 검색
    }

    priorities = tool_priority.get(gap.gap_type, ["tavily", "naver"])

    # 아직 안 쓴 도구 중 우선순위 높은 것
    for tool in priorities:
        if tool not in tried_tools:
            return tool

    # 다 썼으면 첫 번째 반환 (재시도)
    return priorities[0]


def should_continue(
    confidence: float,
    iteration: int,
    max_iterations: int,
    next_action: dict | None
) -> bool:
    """루프 계속 여부 판단

    Args:
        confidence: 정보 충분도
        iteration: 현재 반복 횟수
        max_iterations: 최대 반복
        next_action: 다음 액션 (None이면 종료)

    Returns:
        True면 계속, False면 종료
    """
    # 액션이 없으면 종료
    if next_action is None:
        return False

    # 최대 반복 도달하면 종료
    if iteration >= max_iterations:
        logger.info(f"[Decision] 최대 반복 도달 ({iteration}/{max_iterations}) → 종료")
        return False

    # confidence 충분하면 종료
    if confidence >= settings.AGENT_CONFIDENCE_THRESHOLD:
        return False

    return True
