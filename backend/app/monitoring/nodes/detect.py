"""Detect 노드 - 이벤트 감지

이벤트 유형:
1. article_surge: 특정 이슈에 기사가 급증
2. new_issue: 새로운 이슈 생성됨
3. followed_update: 팔로우한 이슈에 새 기사
4. breaking_news: 속보성 뉴스 감지
"""
import logging
from datetime import datetime, timezone, timedelta, date
from uuid import UUID
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.monitoring.state import MonitoringState, EventData
# 모든 모델 올바른 순서로 로드
import app.core.models  # noqa: F401
from app.issues.models import Issue, IssueArticle, IssueFollow
from app.core.config import settings

logger = logging.getLogger(__name__)

# 한국 시간대
KST = timezone(timedelta(hours=9))

# 이벤트 감지 임계값
SURGE_RATIO = 2.0    # 평균 대비 2배 이상이면 surge


class DetectNode:
    """이벤트 감지 노드"""

    async def __call__(
        self,
        state: MonitoringState,
        db: AsyncSession
    ) -> dict:
        """Detect 노드 실행

        1. 신규 이슈 이벤트 생성
        2. 기사 급증 감지
        3. 팔로우 이슈 업데이트 확인
        """
        matched_results = state.get("matched_results", [])
        new_issues_created = state.get("new_issues_created", [])
        errors = list(state.get("errors", []))

        detected_events: list[EventData] = []

        logger.info("=== 이벤트 감지 시작 ===")

        try:
            # 1. 신규 이슈 이벤트
            new_issue_events = self._detect_new_issues(new_issues_created)
            detected_events.extend(new_issue_events)

            # 2. 기사 급증 감지
            surge_events = await self._detect_article_surge(
                matched_results, db
            )
            detected_events.extend(surge_events)

            # 3. 팔로우 이슈 업데이트
            follow_events = await self._detect_followed_updates(
                matched_results, db
            )
            detected_events.extend(follow_events)

            # 4. 속보성 뉴스 감지
            breaking_events = self._detect_breaking_news(
                state.get("collected_articles", []),
                state.get("extracted_entities", [])
            )
            detected_events.extend(breaking_events)

        except Exception as e:
            logger.error(f"이벤트 감지 실패: {e}")
            errors.append(f"Detect: {str(e)}")

        logger.info(f"=== 이벤트 감지 완료: {len(detected_events)}개 이벤트 ===")

        return {
            "detected_events": detected_events,
            "errors": errors,
            "current_step": "detected",
        }

    def _detect_new_issues(
        self,
        new_issues_created: list[dict]
    ) -> list[EventData]:
        """신규 이슈 이벤트 생성"""
        events = []

        for issue_info in new_issues_created:
            event = EventData(
                event_type="new_issue",
                issue_id=issue_info.get("id"),
                issue_name=issue_info.get("name"),
                data={
                    "category": issue_info.get("category"),
                    "what_type": issue_info.get("what_type"),
                },
            )
            events.append(event)
            logger.info(f"[이벤트] 신규 이슈: {issue_info.get('name')}")

        return events

    async def _detect_article_surge(
        self,
        matched_results: list[dict],
        db: AsyncSession
    ) -> list[EventData]:
        """기사 급증 감지"""
        events = []

        # 이슈별 오늘 기사 수 집계
        issue_article_counts = {}
        for result in matched_results:
            issue_id = result["issue_id"]
            issue_name = result["issue_name"]

            if issue_name == "UNASSIGNED":
                continue

            if issue_id not in issue_article_counts:
                issue_article_counts[issue_id] = {
                    "name": issue_name,
                    "count": 0
                }
            issue_article_counts[issue_id]["count"] += 1

        # 급증 체크
        for issue_id, data in issue_article_counts.items():
            today_count = data["count"]

            if today_count >= settings.SURGE_THRESHOLD:
                # 과거 평균과 비교
                avg_count = await self._get_average_article_count(
                    UUID(issue_id), db
                )

                if avg_count > 0 and today_count >= avg_count * SURGE_RATIO:
                    event = EventData(
                        event_type="article_surge",
                        issue_id=issue_id,
                        issue_name=data["name"],
                        data={
                            "today_count": today_count,
                            "average_count": round(avg_count, 1),
                            "ratio": round(today_count / avg_count, 1),
                        },
                    )
                    events.append(event)
                    logger.info(
                        f"[이벤트] 기사 급증: {data['name']} "
                        f"({today_count}개, 평균 {avg_count:.1f}개)"
                    )
                elif avg_count == 0 and today_count >= settings.SURGE_THRESHOLD:
                    # 기존 데이터 없지만 충분히 많은 경우
                    event = EventData(
                        event_type="article_surge",
                        issue_id=issue_id,
                        issue_name=data["name"],
                        data={
                            "today_count": today_count,
                            "average_count": 0,
                            "ratio": None,
                        },
                    )
                    events.append(event)

        return events

    async def _get_average_article_count(
        self,
        issue_id: UUID,
        db: AsyncSession
    ) -> float:
        """이슈의 일별 평균 기사 수 조회 (최근 7일)"""
        from datetime import datetime, timedelta

        # 최근 7일간의 기사 조회
        week_ago = datetime.now(KST) - timedelta(days=7)
        today = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)

        query = (
            select(func.count(IssueArticle.id))
            .where(IssueArticle.issue_id == issue_id)
            .where(IssueArticle.collected_at >= week_ago)
            .where(IssueArticle.collected_at < today)
        )

        result = await db.execute(query)
        total_count = result.scalar() or 0

        # 일 평균 (7일 기준)
        return total_count / 7.0

    async def _detect_followed_updates(
        self,
        matched_results: list[dict],
        db: AsyncSession
    ) -> list[EventData]:
        """팔로우한 이슈 업데이트 감지"""
        events = []

        # 팔로우된 이슈 ID 조회 (IssueFollow 테이블 통해)
        followed_query = (
            select(Issue.id, Issue.name)
            .join(IssueFollow, Issue.id == IssueFollow.issue_id)
            .distinct()
        )
        result = await db.execute(followed_query)
        followed_issues = {str(row[0]): row[1] for row in result.fetchall()}

        if not followed_issues:
            return events

        # 오늘 매칭된 것 중 팔로우 이슈 찾기
        for result in matched_results:
            issue_id = result["issue_id"]
            if issue_id in followed_issues:
                # 중복 방지
                if not any(e["issue_id"] == issue_id and e["event_type"] == "followed_update" for e in events):
                    event = EventData(
                        event_type="followed_update",
                        issue_id=issue_id,
                        issue_name=followed_issues[issue_id],
                        data={
                            "article_title": result.get("article_title", ""),
                        },
                    )
                    events.append(event)
                    logger.info(
                        f"[이벤트] 팔로우 업데이트: {followed_issues[issue_id]}"
                    )

        return events

    def _detect_breaking_news(
        self,
        articles: list[dict],
        entities: list[dict]
    ) -> list[EventData]:
        """속보성 뉴스 감지

        - 제목에 '속보', '긴급', '단독' 등 포함
        - 주요 인물/사건 유형 조합
        """
        events = []
        ner_map = {e["article_idx"]: e for e in entities}

        BREAKING_KEYWORDS = ["속보", "긴급", "단독", "특보", "BREAKING"]
        IMPORTANT_TYPES = ["TRIAL", "INVESTIGATION", "ACCIDENT"]

        for idx, article in enumerate(articles):
            title = article.get("title", "")

            # 속보 키워드 체크
            is_breaking = any(kw in title for kw in BREAKING_KEYWORDS)

            if is_breaking:
                ner_data = ner_map.get(idx, {})

                event = EventData(
                    event_type="breaking_news",
                    issue_id=None,
                    issue_name=None,
                    data={
                        "title": title,
                        "what_type": ner_data.get("what_type"),
                        "who": [w.get("name") for w in ner_data.get("who", [])],
                    },
                )
                events.append(event)
                logger.info(f"[이벤트] 속보: {title[:50]}")

        return events


# 싱글톤 인스턴스
detect_node = DetectNode()
