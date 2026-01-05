"""일간 다이제스트 생성

하루 동안 수집된 이슈들을 요약해서 다이제스트 생성
"""
import logging
from datetime import datetime, timezone, timedelta, date
from collections import defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from openai import OpenAI

from app.core.config import settings
from app.core.prompts import daily_digest_prompt
from app.issues.models import Issue, IssueArticle, IssueContent, DailyDigest

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class DigestGenerator:
    """일간 다이제스트 생성기"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = "deepseek-chat"

    async def generate_daily_digest(
        self,
        digest_date: date | None = None
    ) -> DailyDigest | None:
        """일간 다이제스트 생성

        Args:
            digest_date: 대상 날짜 (None이면 오늘)

        Returns:
            생성된 DailyDigest 또는 None
        """
        if digest_date is None:
            digest_date = datetime.now(KST).date()

        logger.info(f"=== 일간 다이제스트 생성: {digest_date} ===")

        # 1. 해당 날짜의 이슈들 조회
        issues_by_category = await self._get_issues_by_category(digest_date)

        if not issues_by_category:
            logger.warning(f"다이제스트 생성할 이슈 없음: {digest_date}")
            return None

        total_issues = sum(len(issues) for issues in issues_by_category.values())
        logger.info(f"대상 이슈: {total_issues}개")

        # 2. LLM으로 다이제스트 생성
        summary = await self._generate_summary(digest_date, issues_by_category)

        if not summary:
            logger.error("다이제스트 생성 실패")
            return None

        # 3. 저장 (기존 있으면 업데이트)
        existing = await self.db.execute(
            select(DailyDigest).where(DailyDigest.date == digest_date)
        )
        digest = existing.scalar_one_or_none()

        if digest:
            digest.summary = summary
            logger.info("기존 다이제스트 업데이트")
        else:
            digest = DailyDigest(
                date=digest_date,
                summary=summary
            )
            self.db.add(digest)
            logger.info("새 다이제스트 생성")

        await self.db.flush()

        logger.info(f"=== 다이제스트 생성 완료 ===")
        return digest

    async def _get_issues_by_category(
        self,
        target_date: date
    ) -> dict[str, list[dict]]:
        """카테고리별 이슈 조회"""
        start_of_day = datetime.combine(target_date, datetime.min.time(), tzinfo=KST)
        end_of_day = datetime.combine(target_date, datetime.max.time(), tzinfo=KST)

        # 해당 날짜에 기사가 수집된 이슈들
        stmt = (
            select(Issue)
            .join(IssueArticle)
            .options(
                selectinload(Issue.articles),
                selectinload(Issue.contents)
            )
            .where(
                IssueArticle.collected_at >= start_of_day,
                IssueArticle.collected_at <= end_of_day,
                Issue.status == "active"
            )
            .distinct()
        )
        result = await self.db.execute(stmt)
        issues = result.scalars().all()

        # 카테고리별 그룹화
        by_category: dict[str, list[dict]] = defaultdict(list)

        for issue in issues:
            category = issue.category or "기타"

            # 해당 날짜의 기사 수
            article_count = sum(
                1 for a in issue.articles
                if a.collected_at and start_of_day <= a.collected_at <= end_of_day
            )

            # 최신 콘텐츠 요약
            content_summary = None
            if issue.contents:
                latest = sorted(issue.contents, key=lambda c: c.created_at, reverse=True)[0]
                content_summary = latest.content[:200] if latest.content else None

            by_category[category].append({
                "id": str(issue.id),
                "name": issue.name,
                "summary": issue.what_summary or "",
                "article_count": article_count,
                "content_summary": content_summary,
                "is_new": issue.first_seen_at == target_date,
            })

        # 기사 수로 정렬
        for category in by_category:
            by_category[category].sort(key=lambda x: x["article_count"], reverse=True)

        return dict(by_category)

    async def _generate_summary(
        self,
        digest_date: date,
        issues_by_category: dict[str, list[dict]]
    ) -> str | None:
        """LLM으로 다이제스트 요약 생성"""
        date_str = digest_date.strftime("%Y년 %m월 %d일")

        prompt = daily_digest_prompt(date_str, issues_by_category)

        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.3,
            )

            content = response.choices[0].message.content
            return content if content else None

        except Exception as e:
            logger.error(f"다이제스트 LLM 생성 실패: {e}")
            return None

    async def get_digest(self, digest_date: date) -> dict | None:
        """다이제스트 조회 (없으면 생성)"""
        # 기존 다이제스트 확인
        result = await self.db.execute(
            select(DailyDigest).where(DailyDigest.date == digest_date)
        )
        digest = result.scalar_one_or_none()

        if not digest:
            # 없으면 생성
            digest = await self.generate_daily_digest(digest_date)
            if not digest:
                return None
            await self.db.commit()

        # 카테고리별 이슈 정보 추가
        issues_by_category = await self._get_issues_by_category(digest_date)

        return {
            "date": digest_date,
            "summary": digest.summary,
            "categories": issues_by_category,
            "total_issues": sum(len(v) for v in issues_by_category.values()),
            "created_at": digest.created_at,
        }
