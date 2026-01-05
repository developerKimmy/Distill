"""모니터링 파이프라인

단순 ETL 파이프라인 - 뉴스 수집 → 분류 → 저장

Pipeline: Collect → Extract → Resolve → Match → Enrich → Detect
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
