"""Agent 메인 모듈

1시간마다 실행되어:
1. 뉴스 수집 (Google News RSS + Naver + Tavily)
2. 클러스터링 + 이슈 매칭
3. 이벤트 감지 (기사 급증, 팔로우 업데이트, 신규 이슈)
4. 알림 발송 (인앱 + 이메일)
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.collectors.news import NewsCollector
from app.agent.sensors import (
    ArticleSurgeSensor,
    FollowedUpdateSensor,
    NewIssueSensor,
    Event,
)
from app.agent.notifier import Notifier
from app.batch.models import BatchRun  # IssueDailySnapshot relationship 해결용
from app.notifications.models import AgentRun
from app.issues.service import IssueService

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class MonitoringAgent:
    """모니터링 에이전트

    1시간마다 실행되어 뉴스 수집, 이벤트 감지, 알림 발송
    """

    def __init__(self):
        self.collector = NewsCollector()
        self.sensors = [
            ArticleSurgeSensor(),
            FollowedUpdateSensor(),
            NewIssueSensor(),
        ]
        self.notifier = Notifier()

    async def run_cycle(self, db: AsyncSession) -> AgentRun:
        """한 사이클 실행

        Returns:
            AgentRun: 실행 기록
        """
        agent_run = AgentRun(
            started_at=datetime.now(KST),
            status="running"
        )
        db.add(agent_run)
        await db.flush()

        try:
            # 1. Collect - 뉴스 수집
            logger.info("=== Agent Cycle Started ===")
            logger.info("Step 1: Collecting news...")

            articles = await self.collector.collect(db)
            agent_run.articles_collected = len(articles)
            logger.info(f"Collected {len(articles)} new articles")

            # 2. Analyze - 기존 IssueService 활용하여 클러스터링 + 이슈 매칭
            if articles:
                logger.info("Step 2: Analyzing issues...")
                issue_service = IssueService(db)

                # 기존 collect_issues 대신 간소화된 처리
                # (콘텐츠 생성은 배치에서 하므로 여기서는 스킵)
                issues = await issue_service.collect_issues()
                agent_run.issues_processed = len(issues)
                logger.info(f"Processed {len(issues)} issues")

            await db.commit()

            # 3. Detect - 이벤트 감지
            logger.info("Step 3: Detecting events...")
            all_events: list[Event] = []

            for sensor in self.sensors:
                try:
                    events = await sensor.detect(db)
                    all_events.extend(events)
                    logger.info(f"{sensor.sensor_type}: {len(events)} events")
                except Exception as e:
                    logger.error(f"Sensor error ({sensor.sensor_type}): {e}")

            agent_run.events_detected = len(all_events)
            logger.info(f"Total {len(all_events)} events detected")

            # 4. Act - 알림 발송
            logger.info("Step 4: Sending notifications...")
            notifications_sent = 0

            for event in all_events:
                try:
                    count = await self.notifier.notify(event, db)
                    notifications_sent += count
                except Exception as e:
                    logger.error(f"Notification error: {e}")

            await db.commit()

            agent_run.notifications_sent = notifications_sent
            agent_run.status = "completed"
            agent_run.completed_at = datetime.now(KST)

            logger.info(f"=== Agent Cycle Completed ===")
            logger.info(f"Articles: {agent_run.articles_collected}, "
                       f"Issues: {agent_run.issues_processed}, "
                       f"Events: {agent_run.events_detected}, "
                       f"Notifications: {agent_run.notifications_sent}")

        except Exception as e:
            logger.error(f"Agent cycle failed: {e}")
            agent_run.status = "failed"
            agent_run.error_message = str(e)
            agent_run.completed_at = datetime.now(KST)

        await db.commit()
        return agent_run


async def run_agent_once():
    """Agent 한 번 실행 (테스트/수동 실행용)"""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        agent = MonitoringAgent()
        result = await agent.run_cycle(db)
        return result


if __name__ == "__main__":
    # 직접 실행 시
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_agent_once())
