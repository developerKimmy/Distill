"""모니터링 파이프라인

ETL 파이프라인 + Agent 기반 정보 보강

Pipeline: Collect → Extract → Resolve → Match → [Agent] → Enrich → Detect
"""
import logging
import traceback
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.monitoring.state import MonitoringState
from app.monitoring.nodes import (
    collect_node,
    extract_node,
    resolve_node,
    match_node,
    enrich_node,
    detect_node,
)
from app.core.config import settings
from app.common.utils import EmailService

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


async def run_monitoring(
    db: AsyncSession,
    search_terms: list[str] | None = None,
    use_agent: bool | None = None
) -> MonitoringState:
    """모니터링 파이프라인 실행

    Args:
        db: 데이터베이스 세션
        search_terms: 검색 키워드 (None이면 기본 뉴스 수집)
        use_agent: Agent 사용 여부 (None이면 settings.AGENT_ENABLED)

    Returns:
        최종 State
    """
    run_id = str(uuid4())
    now = datetime.now(KST)
    use_agent = use_agent if use_agent is not None else settings.AGENT_ENABLED

    logger.info(f"=== 모니터링 시작 [{run_id}] (agent={use_agent}) ===")

    state: MonitoringState = {
        "run_id": run_id,
        "started_at": now,
        "collected_articles": [],
        "extracted_entities": [],
        "matched_results": [],
        "new_issues_created": [],
        "enriched_issues": [],
        "detected_events": [],
        "errors": [],
        "current_step": "started",
        "agent_results": [],  # Agent 결과
    }

    try:
        # 1. Collect - 뉴스 수집
        state = {**state, **await collect_node(state, db)}

        # 2. Extract - NER 추출
        state = {**state, **await extract_node(state)}

        # 3. Resolve - Entity 해소 + 1차 검증
        state = {**state, **await resolve_node(state)}

        # 4. Match - 이슈 매칭 + DB 저장
        state = {**state, **await match_node(state, db)}

        # 5. Agent - 기사 부족 이슈에 추가 정보 수집 (NEW)
        if use_agent:
            state = await _run_agents(state)

        # 6. Enrich - 콘텐츠 생성 + 2차 검증
        state = {**state, **await enrich_node(state, db)}

        # 7. Detect - 이벤트 감지
        state = {**state, **await detect_node(state, db)}

        agent_count = len(state.get('agent_results', []))
        logger.info(
            f"=== 모니터링 완료 [{run_id}] ===\n"
            f"  수집: {len(state.get('collected_articles', []))}개\n"
            f"  매칭: {len(state.get('matched_results', []))}개\n"
            f"  신규 이슈: {len(state.get('new_issues_created', []))}개\n"
            f"  Agent 처리: {agent_count}개 이슈\n"
            f"  콘텐츠: {len(state.get('enriched_issues', []))}개\n"
            f"  이벤트: {len(state.get('detected_events', []))}개\n"
            f"  오류: {len(state.get('errors', []))}개"
        )

    except Exception as e:
        logger.error(f"파이프라인 실패: {e}")
        state["errors"].append(str(e))
        state["current_step"] = "failed"

        # 에러 알림 발송
        _send_error_alert(
            error_type="Pipeline Error",
            error_message=str(e),
            location=f"run_monitoring (step: {state.get('current_step', 'unknown')})",
            traceback_str=traceback.format_exc(),
            extra_info={
                "run_id": run_id,
                "collected": len(state.get('collected_articles', [])),
                "matched": len(state.get('matched_results', [])),
            }
        )

    return state


def _send_error_alert(
    error_type: str,
    error_message: str,
    location: str = "",
    traceback_str: str = "",
    extra_info: dict | None = None
) -> None:
    """에러 알림 발송 헬퍼"""
    if not settings.ADMIN_EMAIL:
        return

    try:
        email_service = EmailService(
            gmail_user=settings.GMAIL_USER,
            gmail_app_password=settings.GMAIL_APP_PASSWORD
        )
        email_service.send_error_alert(
            recipient=settings.ADMIN_EMAIL,
            error_type=error_type,
            error_message=error_message,
            location=location,
            traceback_str=traceback_str,
            extra_info=extra_info
        )
    except Exception as e:
        logger.error(f"에러 알림 발송 실패: {e}")


async def _run_agents(state: MonitoringState) -> MonitoringState:
    """기사 부족 이슈에 Agent 실행

    Args:
        state: 현재 파이프라인 상태

    Returns:
        Agent 결과가 추가된 상태
    """
    from app.monitoring.agent import run_issue_agents

    matched_results = state.get("matched_results", [])
    articles = state.get("collected_articles", [])

    if not matched_results:
        return state

    try:
        agent_results = await run_issue_agents(
            matched_results=matched_results,
            articles=articles
        )

        # Agent가 추가 수집한 기사를 articles에 병합
        for agent_state in agent_results:
            # 새로 수집된 기사들
            new_articles = agent_state.get("articles", [])[len(articles):]
            if new_articles:
                logger.info(
                    f"[Agent] {agent_state['issue_name']}: "
                    f"{len(new_articles)}개 기사 추가"
                )

        state["agent_results"] = agent_results
        state["current_step"] = "agent_completed"

    except Exception as e:
        logger.error(f"Agent 실행 실패: {e}")
        state["errors"].append(f"Agent: {str(e)}")

    return state
