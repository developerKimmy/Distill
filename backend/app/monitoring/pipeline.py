"""모니터링 파이프라인

단순 ETL 파이프라인 - 뉴스 수집 → 분류 → 저장

Pipeline: Collect → Extract → Resolve → Match → Enrich → Detect
"""
import logging
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

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


async def run_monitoring(
    db: AsyncSession,
    search_terms: list[str] | None = None
) -> MonitoringState:
    """모니터링 파이프라인 실행

    Args:
        db: 데이터베이스 세션
        search_terms: 검색 키워드 (None이면 기본 뉴스 수집)

    Returns:
        최종 State
    """
    run_id = str(uuid4())
    now = datetime.now(KST)

    logger.info(f"=== 모니터링 시작 [{run_id}] ===")

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

        # 5. Enrich - 콘텐츠 생성 + 2차 검증
        state = {**state, **await enrich_node(state, db)}

        # 6. Detect - 이벤트 감지
        state = {**state, **await detect_node(state, db)}

        logger.info(
            f"=== 모니터링 완료 [{run_id}] ===\n"
            f"  수집: {len(state.get('collected_articles', []))}개\n"
            f"  매칭: {len(state.get('matched_results', []))}개\n"
            f"  신규 이슈: {len(state.get('new_issues_created', []))}개\n"
            f"  콘텐츠: {len(state.get('enriched_issues', []))}개\n"
            f"  이벤트: {len(state.get('detected_events', []))}개\n"
            f"  오류: {len(state.get('errors', []))}개"
        )

    except Exception as e:
        logger.error(f"파이프라인 실패: {e}")
        state["errors"].append(str(e))
        state["current_step"] = "failed"

    return state
