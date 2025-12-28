"""Agent Celery 태스크"""
import asyncio
import logging

from app.core.celery_app import celery_app
from app.core.database import create_async_session_factory

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.agent.run_agent_cycle")
def run_agent_cycle(self):
    """Agent 한 사이클 실행 (1시간마다)

    뉴스 수집 → 클러스터링 → 이벤트 감지 → 알림 발송
    """
    logger.info("=== Agent Task Started ===")

    async def _run():
        from app.agent.main import MonitoringAgent

        # Celery에서 asyncio.run()으로 호출되므로 매번 새 엔진 생성 필요
        AsyncSession = create_async_session_factory()

        async with AsyncSession() as db:
            try:
                agent = MonitoringAgent()
                result = await agent.run_cycle(db)

                return {
                    "status": result.status,
                    "articles_collected": result.articles_collected,
                    "issues_processed": result.issues_processed,
                    "events_detected": result.events_detected,
                    "notifications_sent": result.notifications_sent,
                    "error": result.error_message,
                }
            except Exception as e:
                logger.error(f"Agent task failed: {e}")
                return {
                    "status": "failed",
                    "error": str(e),
                }

    result = asyncio.run(_run())
    logger.info(f"=== Agent Task Completed: {result} ===")
    return result
