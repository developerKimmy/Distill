import time
import numpy as np
from uuid import UUID
from datetime import date, datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# 한국 시간대 (UTC+9)
KST = timezone(timedelta(hours=9))

# 임베딩 유사도 임계값 (높을수록 엄격하게 매칭, 새 이슈 생성 증가)
SIMILARITY_THRESHOLD = 0.92

from app.issues.models import (
    Issue, IssueDailySnapshot, IssueArticle, IssueKeyword, IssueEmbedding, IssueFollow
)
from app.insights.models import IssueInsight
from app.core.agent.tools import (
    NaverNewsProvider, ClusteringProvider, KeywordProvider,
    YouTubeProvider, NeedsProvider, YouTubeAPIError, EmbeddingProvider
)
from app.content.service import ContentService
from app.common.utils import ArticleDeduplicator, PipelineResult


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """코사인 유사도 계산"""
    a_np = np.array(a)
    b_np = np.array(b)
    return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np)))


class IssueService:
    """이슈 수집 + 조회 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.news_provider = NaverNewsProvider()
        self.clustering_provider = ClusteringProvider()
        self.keyword_provider = KeywordProvider()
        self.youtube_provider = YouTubeProvider()
        self.needs_provider = NeedsProvider()
        self.embedding_provider = EmbeddingProvider()
        self.content_service = ContentService(db)
        self.deduplicator = ArticleDeduplicator()

    async def _find_similar_issue(self, name: str, summary: str) -> tuple[Issue | None, float]:
        """임베딩 기반으로 유사한 기존 이슈 찾기

        Returns:
            (Issue, similarity) or (None, 0.0)
        """
        # 새 이슈의 임베딩 생성
        text_to_embed = f"{name}: {summary}"
        new_embedding = self.embedding_provider.embed(text_to_embed)

        # 활성 이슈 중 임베딩이 있는 것들 조회
        result = await self.db.execute(
            select(Issue).where(
                Issue.status == "active",
                Issue.name_embedding.isnot(None)
            )
        )
        active_issues = result.scalars().all()

        best_match = None
        best_similarity = 0.0

        for issue in active_issues:
            similarity = cosine_similarity(new_embedding, list(issue.name_embedding))
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = issue

        # 임계값 이상이면 반환
        if best_similarity >= SIMILARITY_THRESHOLD:
            print(f"[ISSUE]   Found similar issue: '{best_match.name}' (similarity: {best_similarity:.3f})")
            return best_match, best_similarity

        return None, best_similarity

    async def collect_issues(self, batch_run_id: UUID | None = None) -> list[Issue]:
        """이슈 수집 파이프라인

        Steps:
        1. 랭킹 뉴스 스크래핑
        2. 클러스터링 (LLM)
        3. 이슈별 처리 시작
        4. 기사 검색 + 중복 제거
        5. 키워드 추출
        6. YouTube 수집
        7. 임베딩 생성
        7.5. 후속 검색 (진행형 이슈)
        8. 콘텐츠 생성 + 팩트체크
        """
        today = datetime.now(KST).date()  # 한국 시간 기준
        total_start = time.time()
        pipeline_result = PipelineResult()
        self.deduplicator.reset()  # 중복 제거기 초기화

        print(f"[ISSUE] ========== collect_issues started ==========")

        # 1. 랭킹 뉴스 스크래핑
        step_start = time.time()
        print(f"[ISSUE] Step 1: Scraping ranking news...")
        try:
            news_list = self.news_provider.get_ranking_news()
            titles = [news.title for news in news_list]
            print(f"[ISSUE] Step 1 completed: {len(titles)} news titles in {time.time() - step_start:.2f}s")
        except Exception as e:
            print(f"[ISSUE] Step 1 FAILED: {e}")
            raise

        # 기존 active 이슈 목록 조회
        result = await self.db.execute(
            select(Issue.name).where(Issue.status == "active")
        )
        existing_issues = result.scalars().all()

        # 2. 클러스터링 (기존 이슈 전달)
        step_start = time.time()
        print(f"[ISSUE] Step 2: Clustering news...")
        try:
            clustered = self.clustering_provider.cluster_news(titles, existing_issues=existing_issues)
            print(f"[ISSUE] Step 2 completed: {len(clustered)} clusters in {time.time() - step_start:.2f}s")
        except Exception as e:
            print(f"[ISSUE] Step 2 FAILED: {e}")
            raise

        # 3. 이슈별 처리
        issues = []
        snapshot_ids = []
        print(f"[ISSUE] Step 3: Processing {len(clustered)} issues...")

        for idx, item in enumerate(clustered):
            issue_start = time.time()
            print(f"[ISSUE] --- Processing issue {idx+1}/{len(clustered)}: {item.name} (type: {item.issue_type}) ---")

            try:
                # 임베딩 기반 유사 이슈 찾기
                existing_issue, similarity = await self._find_similar_issue(item.name, item.summary)

                # 새 이슈의 임베딩 생성 (저장용)
                text_to_embed = f"{item.name}: {item.summary}"
                new_embedding = self.embedding_provider.embed(text_to_embed)

                if existing_issue:
                    issue = existing_issue
                    issue.last_seen_at = today
                    issue.total_snapshots += 1
                    print(f"[ISSUE]   Matched to existing issue: '{issue.name}' (similarity: {similarity:.3f})")
                else:
                    issue = Issue(
                        name=item.name,
                        category=item.category,
                        first_seen_at=today,
                        last_seen_at=today,
                        total_snapshots=1,
                        status="active",
                        name_embedding=new_embedding  # 임베딩 저장
                    )
                    self.db.add(issue)
                    await self.db.flush()
                    print(f"[ISSUE]   Created new issue: '{item.name}'")

                # 일간 스냅샷 생성
                snapshot = IssueDailySnapshot(
                    issue_id=issue.id,
                    batch_run_id=batch_run_id,
                    date=today,
                    article_count=len(item.article_indices),
                    sentiment_score=None,
                    summary=item.summary
                )
                self.db.add(snapshot)
                await self.db.flush()

                # 4. 네이버 API로 기사 상세 검색 + 중복 제거
                step_start = time.time()
                print(f"[ISSUE]   Step 4: Searching news articles for '{item.name}'...")
                articles = self.news_provider.search_news(item.name, display=10)

                article_dicts = []
                saved_count = 0
                earliest_pub_date = None  # 가장 이른 pub_date 추적
                for article in articles:
                    # 중복 체크
                    if self.deduplicator.is_duplicate(article.url, article.title, article.description or ""):
                        continue

                    self.deduplicator.add(article.url, article.title, article.description or "")
                    issue_article = IssueArticle(
                        snapshot_id=snapshot.id,
                        title=article.title,
                        description=article.description,
                        url=article.url,
                        press=article.press,
                        published_at=article.published_at
                    )
                    self.db.add(issue_article)
                    article_dicts.append({
                        "title": article.title,
                        "description": article.description,
                        "url": article.url
                    })
                    saved_count += 1

                    # 가장 이른 pub_date 추적
                    if article.published_at:
                        pub_date = article.published_at.date() if hasattr(article.published_at, 'date') else article.published_at
                        if earliest_pub_date is None or pub_date < earliest_pub_date:
                            earliest_pub_date = pub_date

                # first_seen_at 갱신 (더 이른 날짜가 발견된 경우)
                if earliest_pub_date and earliest_pub_date < issue.first_seen_at:
                    print(f"[ISSUE]   Updating first_seen_at: {issue.first_seen_at} -> {earliest_pub_date}")
                    issue.first_seen_at = earliest_pub_date

                print(f"[ISSUE]   Step 4 completed: {saved_count}/{len(articles)} articles (중복 제거) in {time.time() - step_start:.2f}s")

                # 5. 키워드 추출
                step_start = time.time()
                print(f"[ISSUE]   Step 5: Extracting keywords...")
                keywords = []
                if article_dicts:
                    try:
                        extracted = self.keyword_provider.extract_keywords(item.name, article_dicts)
                        print(f"[ISSUE]   Step 5 completed: {len(extracted.keywords)} keywords in {time.time() - step_start:.2f}s")
                        for keyword in extracted.keywords:
                            issue_keyword = IssueKeyword(
                                snapshot_id=snapshot.id,
                                keyword=keyword
                            )
                            self.db.add(issue_keyword)
                            keywords.append(keyword)
                    except Exception as e:
                        print(f"[ISSUE]   Step 5 WARNING: 키워드 추출 실패 - {e}")

                # 6. YouTube 수집
                step_start = time.time()
                print(f"[ISSUE]   Step 6: Collecting YouTube videos and comments...")
                comments = await self._collect_youtube(snapshot.id, item.name)
                print(f"[ISSUE]   Step 6 completed: {len(comments)} comments in {time.time() - step_start:.2f}s")

                # 7. 임베딩 생성
                step_start = time.time()
                print(f"[ISSUE]   Step 7: Creating embeddings...")
                await self._create_embeddings(snapshot.id, snapshot.date, item.name, article_dicts, keywords, comments)
                print(f"[ISSUE]   Step 7 completed in {time.time() - step_start:.2f}s")

                # 7.5 후속 검색 (진행형 이슈만)
                if item.issue_type == "ongoing" and item.related_search_terms:
                    step_start = time.time()
                    print(f"[ISSUE]   Step 7.5: Follow-up search for ongoing issue...")
                    followup_count = await self._follow_up_search(
                        snapshot.id,
                        item.related_search_terms,
                        existing_urls={a["url"] for a in article_dicts}
                    )
                    print(f"[ISSUE]   Step 7.5 completed: {followup_count} additional articles in {time.time() - step_start:.2f}s")

                print(f"[ISSUE] --- Issue {idx+1} completed in {time.time() - issue_start:.2f}s ---")
                issues.append(issue)
                snapshot_ids.append(snapshot.id)
                pipeline_result.add_success(issue)

            except Exception as e:
                print(f"[ISSUE] --- Issue {idx+1} FAILED: {e} ---")
                pipeline_result.add_failure(item, e)
                continue  # 다음 이슈로 계속 진행

        # 중간 커밋
        await self.db.commit()
        print(f"[ISSUE] Issue processing: {pipeline_result.summary()}")
        print(f"[ISSUE] Starting content generation...")

        # 8. 콘텐츠 생성 + 팩트체크
        step_start = time.time()
        print(f"[ISSUE] Step 8: Generating content for {len(snapshot_ids)} snapshots...")
        for i, snapshot_id in enumerate(snapshot_ids):
            try:
                content_start = time.time()
                print(f"[ISSUE]   Generating content {i+1}/{len(snapshot_ids)}...")

                # 상태: processing
                await self.db.execute(
                    select(IssueDailySnapshot).where(IssueDailySnapshot.id == snapshot_id)
                )
                snapshot_to_update = await self.db.get(IssueDailySnapshot, snapshot_id)
                if snapshot_to_update:
                    snapshot_to_update.content_status = "processing"
                    await self.db.flush()

                content = await self.content_service.generate_content(snapshot_id)

                # 8.5 팩트체크 (콘텐츠 생성 후)
                if content:
                    await self.content_service.verify_content(content.id)

                # 상태: completed
                if snapshot_to_update:
                    snapshot_to_update.content_status = "completed"
                    await self.db.flush()

                print(f"[ISSUE]   Content {i+1} generated in {time.time() - content_start:.2f}s")
            except Exception as e:
                print(f"[ISSUE]   Content generation error (snapshot: {snapshot_id}): {e}")
                # 상태: failed
                try:
                    snapshot_to_update = await self.db.get(IssueDailySnapshot, snapshot_id)
                    if snapshot_to_update:
                        snapshot_to_update.content_status = "failed"
                        await self.db.flush()
                except Exception:
                    pass
        print(f"[ISSUE] Step 8 completed in {time.time() - step_start:.2f}s")

        await self.db.commit()
        print(f"[ISSUE] ========== collect_issues completed in {time.time() - total_start:.2f}s ==========")
        print(f"[ISSUE] Final result: {pipeline_result.summary()}")
        return issues

    async def _follow_up_search(
        self,
        snapshot_id: UUID,
        search_terms: list[str],
        existing_urls: set[str]
    ) -> int:
        """후속 검색 - 진행형 이슈에 대해 추가 기사 수집

        Args:
            snapshot_id: 스냅샷 ID
            search_terms: 검색할 엔티티 (인물명, 기관명 등)
            existing_urls: 이미 수집된 기사 URL들

        Returns:
            추가된 기사 수
        """
        added_count = 0

        for term in search_terms[:2]:  # 최대 2개 검색어만
            try:
                articles = self.news_provider.search_news(term, display=5, sort="date")

                for article in articles:
                    # 이미 수집된 기사 스킵
                    if article.url in existing_urls:
                        continue

                    # 중복 체크
                    if self.deduplicator.is_duplicate(article.url, article.title, article.description or ""):
                        continue

                    self.deduplicator.add(article.url, article.title, article.description or "")
                    issue_article = IssueArticle(
                        snapshot_id=snapshot_id,
                        title=article.title,
                        description=article.description,
                        url=article.url,
                        press=article.press,
                        published_at=article.published_at
                    )
                    self.db.add(issue_article)
                    existing_urls.add(article.url)
                    added_count += 1

            except Exception as e:
                print(f"[ISSUE]     Follow-up search error for '{term}': {e}")

        return added_count

    async def _collect_youtube(self, snapshot_id: UUID, issue_name: str) -> list[dict]:
        """YouTube 댓글 수집 + 니즈 분석. 댓글 반환 (DB 저장 없음)."""
        all_comments = []

        try:
            videos = await self.youtube_provider.search_videos(issue_name, max_results=3)
            if not videos:
                return []

            for video in videos:
                # 댓글만 수집 (영상/댓글 DB 저장 안함 - 임베딩용으로만 사용)
                comments = await self.youtube_provider.get_top_comments(video["video_id"], max_results=10)
                for comment in comments:
                    all_comments.append({
                        "text": comment["text"],
                        "like_count": comment["like_count"]
                    })

            if all_comments:
                extracted = self.needs_provider.extract_needs(issue_name, all_comments)
                if extracted.needs or extracted.content_directions:
                    insight = IssueInsight(
                        snapshot_id=snapshot_id,
                        verified_angles={"needs": extracted.needs},
                        content_directions={"directions": extracted.content_directions}
                    )
                    self.db.add(insight)

        except YouTubeAPIError as e:
            print(f"YouTube API 에러 (이슈: {issue_name}): {e}")
        except Exception as e:
            print(f"YouTube 수집 에러 (이슈: {issue_name}): {e}")

        return all_comments

    async def _create_embeddings(
        self,
        snapshot_id: UUID,
        snapshot_date: date,
        issue_name: str,
        articles: list[dict],
        keywords: list[str],
        comments: list[dict]
    ) -> None:
        """임베딩 생성 및 저장 (날짜 컨텍스트 포함)"""
        try:
            embeddings_to_create = []
            date_prefix = f"({snapshot_date.strftime('%m/%d')} 기준)"

            for article in articles:
                if article.get("description"):
                    content = f"{date_prefix} {issue_name}: {article['title']} - {article['description']}"
                    embeddings_to_create.append({
                        "content_type": "article",
                        "content": content
                    })

            for keyword in keywords:
                content = f"{date_prefix} {issue_name}: {keyword}"
                embeddings_to_create.append({
                    "content_type": "keyword",
                    "content": content
                })

            for comment in comments[:10]:
                content = f"{date_prefix} {issue_name}: {comment['text']}"
                embeddings_to_create.append({
                    "content_type": "comment",
                    "content": content
                })

            if not embeddings_to_create:
                return

            texts = [e["content"] for e in embeddings_to_create]
            vectors = self.embedding_provider.embed_batch(texts)

            for i, emb_data in enumerate(embeddings_to_create):
                issue_embedding = IssueEmbedding(
                    snapshot_id=snapshot_id,
                    content_type=emb_data["content_type"],
                    content=emb_data["content"],
                    embedding=vectors[i]
                )
                self.db.add(issue_embedding)

        except Exception as e:
            print(f"임베딩 생성 에러 (이슈: {issue_name}): {e}")

    async def list_issues_for_calendar(
        self,
        categories: list[str] | None = None
    ) -> list[Issue]:
        """달력용 경량 이슈 목록 조회 (completed 스냅샷이 있는 이슈만)"""
        # completed 스냅샷이 있는 이슈만 조회
        stmt = (
            select(Issue)
            .join(IssueDailySnapshot)
            .where(IssueDailySnapshot.content_status == "completed")
        )
        if categories:
            stmt = stmt.where(Issue.category.in_(categories))
        stmt = stmt.distinct().order_by(Issue.last_seen_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_issues(
        self,
        page: int = 1,
        size: int = 20,
        categories: list[str] | None = None
    ) -> tuple[list[Issue], int]:
        """이슈 목록 조회 (completed 스냅샷이 있는 이슈만)"""
        from app.issues.models import IssueContent
        offset = (page - 1) * size

        # completed 스냅샷이 있는 이슈만 카운트
        count_stmt = (
            select(func.count(func.distinct(Issue.id)))
            .join(IssueDailySnapshot)
            .where(IssueDailySnapshot.content_status == "completed")
        )
        if categories:
            count_stmt = count_stmt.where(Issue.category.in_(categories))
        result = await self.db.execute(count_stmt)
        total = result.scalar()

        # completed 스냅샷이 있는 이슈 조회
        stmt = (
            select(Issue)
            .join(IssueDailySnapshot)
            .where(IssueDailySnapshot.content_status == "completed")
            .options(
                selectinload(Issue.snapshots.and_(
                    IssueDailySnapshot.content_status == "completed"
                )).selectinload(IssueDailySnapshot.contents)
            )
        )
        if categories:
            stmt = stmt.where(Issue.category.in_(categories))
        stmt = stmt.distinct().order_by(Issue.last_seen_at.desc()).offset(offset).limit(size)

        result = await self.db.execute(stmt)
        issues = list(result.scalars().all())

        return issues, total

    async def get_issue(self, issue_id: UUID) -> Issue | None:
        """이슈 상세 조회 (completed 스냅샷만)"""
        stmt = (
            select(Issue)
            .options(
                selectinload(Issue.snapshots.and_(
                    IssueDailySnapshot.content_status == "completed"
                )).selectinload(IssueDailySnapshot.articles),
                selectinload(Issue.snapshots.and_(
                    IssueDailySnapshot.content_status == "completed"
                )).selectinload(IssueDailySnapshot.keywords),
                selectinload(Issue.snapshots.and_(
                    IssueDailySnapshot.content_status == "completed"
                )).selectinload(IssueDailySnapshot.insights),
                selectinload(Issue.snapshots.and_(
                    IssueDailySnapshot.content_status == "completed"
                )).selectinload(IssueDailySnapshot.contents)
            )
            .where(Issue.id == issue_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_daily_report(
        self,
        report_date: date,
        categories: list[str] | None = None
    ) -> list[IssueDailySnapshot]:
        """일간 리포트 조회 (completed 스냅샷만)"""
        stmt = (
            select(IssueDailySnapshot)
            .join(Issue)
            .options(
                selectinload(IssueDailySnapshot.issue),
                selectinload(IssueDailySnapshot.articles),
                selectinload(IssueDailySnapshot.keywords),
                selectinload(IssueDailySnapshot.insights),
                selectinload(IssueDailySnapshot.contents)
            )
            .where(
                IssueDailySnapshot.date == report_date,
                IssueDailySnapshot.content_status == "completed"
            )
        )
        if categories:
            stmt = stmt.where(Issue.category.in_(categories))
        stmt = stmt.order_by(IssueDailySnapshot.article_count.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_batch_dates(
        self,
        year: int,
        month: int,
        categories: list[str] | None = None
    ) -> list[date]:
        """배치 실행된 날짜 목록 (completed 스냅샷만)"""
        stmt = select(IssueDailySnapshot.date).where(
            func.extract('year', IssueDailySnapshot.date) == year,
            func.extract('month', IssueDailySnapshot.date) == month,
            IssueDailySnapshot.content_status == "completed"
        )
        if categories:
            stmt = stmt.join(Issue).where(Issue.category.in_(categories))
        stmt = stmt.distinct().order_by(IssueDailySnapshot.date)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ========== 팔로우 관련 메서드 ==========

    async def follow_issue(self, user_id: UUID, issue_id: UUID) -> IssueFollow:
        """이슈 팔로우"""
        # 이미 팔로우 중인지 확인
        existing = await self.db.execute(
            select(IssueFollow).where(
                IssueFollow.user_id == user_id,
                IssueFollow.issue_id == issue_id
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("이미 팔로우 중인 이슈입니다")

        follow = IssueFollow(user_id=user_id, issue_id=issue_id)
        self.db.add(follow)
        await self.db.commit()
        return follow

    async def unfollow_issue(self, user_id: UUID, issue_id: UUID) -> bool:
        """이슈 언팔로우"""
        result = await self.db.execute(
            select(IssueFollow).where(
                IssueFollow.user_id == user_id,
                IssueFollow.issue_id == issue_id
            )
        )
        follow = result.scalar_one_or_none()
        if not follow:
            return False

        await self.db.delete(follow)
        await self.db.commit()
        return True

    async def is_following(self, user_id: UUID, issue_id: UUID) -> bool:
        """팔로우 여부 확인"""
        result = await self.db.execute(
            select(IssueFollow).where(
                IssueFollow.user_id == user_id,
                IssueFollow.issue_id == issue_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_followed_issues(self, user_id: UUID) -> list[Issue]:
        """팔로우한 이슈 목록 조회"""
        result = await self.db.execute(
            select(Issue)
            .join(IssueFollow)
            .where(IssueFollow.user_id == user_id)
            .order_by(IssueFollow.created_at.desc())
        )
        return list(result.scalars().all())