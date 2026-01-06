"""Agent Celery 태스크"""
import asyncio
import logging
import traceback

from app.core.celery_app import celery_app
from app.core.database import create_async_session_factory
from app.core.config import settings
from app.common.utils import EmailService

logger = logging.getLogger(__name__)


def _send_error_alert(error_type: str, error_message: str, traceback_str: str = ""):
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
            location="Agent Task",
            traceback_str=traceback_str
        )
    except Exception as e:
        logger.error(f"에러 알림 발송 실패: {e}")


@celery_app.task(bind=True, name="app.tasks.agent.run_agent_cycle")
def run_agent_cycle(self):
    """Agent 한 사이클 실행 (1시간마다)

    뉴스 수집 → 클러스터링 → 이벤트 감지 → 알림 발송
    """
    logger.info("=== Agent Task Started ===")

    async def _run():
        from app.monitoring.pipeline import run_monitoring

        # Celery에서 asyncio.run()으로 호출되므로 매번 새 엔진 생성 필요
        AsyncSession = create_async_session_factory()

        async with AsyncSession() as db:
            state = await run_monitoring(db)

            return {
                "status": "completed" if not state.get("errors") else "failed",
                "articles_collected": len(state.get("collected_articles", [])),
                "issues_processed": len(state.get("matched_results", [])),
                "events_detected": len(state.get("detected_events", [])),
                "notifications_sent": 0,  # TODO: 알림 개수 추적
                "error": ", ".join(state.get("errors", [])) if state.get("errors") else None,
            }

    try:
        result = asyncio.run(_run())
        logger.info(f"=== Agent Task Completed: {result} ===")
        return result
    except Exception as e:
        logger.error(f"Agent task failed: {e}")
        _send_error_alert(
            error_type="Agent Task Error",
            error_message=str(e),
            traceback_str=traceback.format_exc()
        )
        return {
            "status": "failed",
            "error": str(e),
        }
