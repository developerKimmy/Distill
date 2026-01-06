"""Match 노드 - 이슈 매칭 + 기사 저장

매칭 전략:
1. Entity-first: NER로 추출한 who가 기존 이슈의 entities와 일치하는지 확인
2. Embedding cross-check: Entity 매칭된 이슈들 중 임베딩 유사도 비교
3. 둘 다 통과해야 매칭, 아니면 새 이슈 생성
"""
import logging
from datetime import datetime, timezone, timedelta, date
from uuid import UUID
from sqlalchemy import select, text, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.monitoring.state import (
    MonitoringState, ArticleData, NERData, MatchResult
)
from app.core.agent.tools import EmbeddingProvider
from app.monitoring.collectors import NaverNewsProvider
# 모든 모델 올바른 순서로 로드
import app.core.models  # noqa: F401
from app.issues.models import (
    Issue, IssueArticle, IssueEmbedding, Entity, IssueEntity,
    UNASSIGNED_ISSUE_ID
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# 한국 시간대
KST = timezone(timedelta(hours=9))


class MatchNode:
    """이슈 매칭 노드"""

    def __init__(self):
        self.embedding_provider = EmbeddingProvider()
        self.naver = NaverNewsProvider()

    async def __call__(
        self,
        state: MonitoringState,
        db: AsyncSession
    ) -> dict:
        """Match 노드 실행

        1. 각 기사에 대해 가장 유사한 이슈 찾기
        2. 유사도가 임계값 이상이면 매칭
        3. 아니면 새 이슈 생성 또는 UNASSIGNED
        4. 기사를 DB에 저장
        """
        articles = state.get("collected_articles", [])
        entities = state.get("extracted_entities", [])
        errors = list(state.get("errors", []))

        matched_results: list[MatchResult] = []
        new_issues_created: list[dict] = []

        if not articles:
            logger.info("매칭할 기사 없음")
            return {
                "matched_results": [],
                "new_issues_created": [],
                "errors": errors,
                "current_step": "matched",
            }

        logger.info(f"=== 이슈 매칭 시작: {len(articles)}개 기사 ===")

        # NER 데이터를 article_idx로 인덱싱
        ner_map = {e["article_idx"]: e for e in entities}

        for idx, article in enumerate(articles):
            try:
                ner_data = ner_map.get(idx)
                result, new_issue = await self._match_article(
                    idx, article, ner_data, db
                )
                matched_results.append(result)

                if new_issue:
                    new_issues_created.append(new_issue)

                # 매 10개마다 중간 커밋 (안정성 향상)
                if (idx + 1) % 10 == 0:
                    try:
                        await db.commit()
                        logger.debug(f"중간 커밋 완료: {idx + 1}개")
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"기사 매칭 실패 [{idx}]: {e}")
                errors.append(f"Match [{idx}]: {str(e)}")

                # 트랜잭션 오류 시 rollback 후 계속 진행
                try:
                    await db.rollback()
                except Exception:
                    pass

                # 실패한 기사는 스킵하고 계속 진행
                continue

        try:
            await db.commit()
        except Exception as commit_err:
            logger.error(f"최종 커밋 실패: {commit_err}")
            try:
                await db.rollback()
            except Exception:
                pass

        logger.info(
            f"=== 매칭 완료: {len(matched_results)}개 기사, "
            f"{len(new_issues_created)}개 신규 이슈 ==="
        )

        return {
            "matched_results": matched_results,
            "new_issues_created": new_issues_created,
            "errors": errors,
            "current_step": "matched",
        }

    async def _match_article(
        self,
        idx: int,
        article: ArticleData,
        ner_data: NERData | None,
        db: AsyncSession
    ) -> tuple[MatchResult, dict | None]:
        """단일 기사 매칭 (Entity-first + Embedding cross-check)"""

        embedding = article.get("embedding")
        if not embedding:
            return await self._save_to_unassigned(idx, article, ner_data, db), None

        # NER에서 who 추출
        who_list = ner_data.get("who", []) if ner_data else []
        entity_names = [w.get("name") for w in who_list if w.get("name")]

        # Step 1: Entity 매칭 - who가 연결된 이슈들 찾기
        entity_matched_issues = []
        if entity_names:
            entity_matched_issues = await self._find_issues_by_entities(
                entity_names, db
            )
            logger.debug(
                f"[{idx}] Entity '{entity_names}' → {len(entity_matched_issues)}개 이슈 후보"
            )

        # Step 2: Entity 매칭된 이슈들 중 임베딩 비교
        best_match = None
        if entity_matched_issues:
            best_match = await self._find_best_embedding_match(
                embedding, entity_matched_issues, db
            )

            if best_match and best_match["similarity"] >= settings.EMBEDDING_MATCH_THRESHOLD:
                # Entity ✓ + Embedding ✓ → 매칭
                return await self._finalize_match(
                    idx, article, ner_data, best_match, db
                ), None

            # Entity ✓ + Embedding ✗ → 같은 인물, 다른 사건 → 새 이슈
            logger.debug(
                f"[{idx}] Entity 매칭됐지만 임베딩 낮음 → 새 이슈"
            )

        # Step 3: Entity 매칭 없으면 전체 이슈 대상 높은 임베딩 체크 (alias 가능성)
        if not entity_matched_issues:
            high_sim_match = await self._find_high_similarity_match(embedding, db)

            if high_sim_match:
                # Entity 충돌 체크: 기사 who와 이슈 primary entity가 다르면 매칭 거부
                if entity_names:
                    issue_entities = await self._get_issue_primary_entities(
                        UUID(high_sim_match["issue_id"]), db
                    )
                    if issue_entities and not any(e in entity_names for e in issue_entities):
                        # 기사 who와 이슈 entity가 완전히 다름 → 충돌 → 매칭 거부
                        logger.debug(
                            f"[{idx}] Entity 충돌로 매칭 거부: "
                            f"기사={entity_names}, 이슈={issue_entities}"
                        )
                    else:
                        # 충돌 없음 → 매칭
                        logger.info(
                            f"[{idx}] 높은 유사도 매칭: {high_sim_match['issue_name']} "
                            f"(sim={high_sim_match['similarity']:.2f})"
                        )
                        return await self._finalize_match(
                            idx, article, ner_data, high_sim_match, db
                        ), None
                else:
                    # 기사에 who가 없으면 임베딩만으로 매칭
                    logger.info(
                        f"[{idx}] 높은 유사도 매칭 (no who): {high_sim_match['issue_name']} "
                        f"(sim={high_sim_match['similarity']:.2f})"
                    )
                    return await self._finalize_match(
                        idx, article, ner_data, high_sim_match, db
                    ), None

        # Step 4: 새 이슈 생성 조건 확인
        # who가 있고 what_summary 또는 what_type이 있으면 → 새 이슈 생성
        if ner_data and self._should_create_issue(ner_data):
            issue, new_issue_info = await self._create_new_issue(
                article, ner_data, db
            )
            await self._save_article(article, ner_data, issue.id, db)

            logger.info(f"[{idx}] 신규 이슈 생성: {issue.name}")

            # 새 이슈로 Naver 검색해서 추가 기사 수집
            naver_count = await self._fetch_naver_articles(issue, db)
            if naver_count > 0:
                logger.info(f"[{idx}] Naver 추가 수집: {naver_count}개")
                new_issue_info["naver_articles"] = naver_count

            return MatchResult(
                article_idx=idx,
                issue_id=str(issue.id),
                issue_name=issue.name,
                is_new_issue=True,
                similarity=0.0,
            ), new_issue_info

        # Step 5: UNASSIGNED 승격 체크
        # 기존 UNASSIGNED 기사들 중 유사한 게 있으면 → 함께 새 이슈로 승격
        if embedding:
            promotion_result = await self._try_promote_with_unassigned(
                idx, article, ner_data, embedding, db
            )
            if promotion_result:
                return promotion_result

        # Step 6: UNASSIGNED로 저장 (나중에 유사 기사가 오면 함께 승격됨)
        return await self._save_to_unassigned(idx, article, ner_data, db), None

    def _should_create_issue(self, ner_data: NERData) -> bool:
        """새 이슈 생성 여부 판단"""
        who = ner_data.get("who", [])
        what_summary = ner_data.get("what_summary")
        what_type = ner_data.get("what_type")

        # who가 있고 (what_summary 또는 what_type이 있으면) 이슈 생성
        return len(who) > 0 and (what_summary or what_type)

    async def _finalize_match(
        self,
        idx: int,
        article: ArticleData,
        ner_data: NERData | None,
        match_info: dict,
        db: AsyncSession
    ) -> MatchResult:
        """매칭 확정 및 저장"""
        issue_id = match_info["issue_id"]
        issue_name = match_info["issue_name"]
        similarity = match_info["similarity"]

        await self._save_article(article, ner_data, UUID(issue_id), db)
        await self._update_issue_dates(UUID(issue_id), db)

        logger.debug(f"[{idx}] 매칭: {issue_name} (sim={similarity:.2f})")

        return MatchResult(
            article_idx=idx,
            issue_id=issue_id,
            issue_name=issue_name,
            is_new_issue=False,
            similarity=similarity,
        )

    async def _get_issue_primary_entities(
        self,
        issue_id: UUID,
        db: AsyncSession
    ) -> list[str]:
        """이슈의 primary entity 이름들 조회"""
        query = (
            select(Entity.name)
            .join(IssueEntity, Entity.id == IssueEntity.entity_id)
            .where(IssueEntity.issue_id == issue_id)
            .where(IssueEntity.role == "primary")
        )
        result = await db.execute(query)
        return [row[0] for row in result.fetchall()]

    async def _find_issues_by_entities(
        self,
        entity_names: list[str],
        db: AsyncSession
    ) -> list[dict]:
        """Entity 이름으로 연결된 이슈들 찾기"""
        if not entity_names:
            return []

        # SQLAlchemy ORM 쿼리 사용
        query = (
            select(
                Issue.id,
                Issue.name,
                Issue.name_embedding
            )
            .join(IssueEntity, Issue.id == IssueEntity.issue_id)
            .join(Entity, IssueEntity.entity_id == Entity.id)
            .where(Entity.name.in_(entity_names))
            .where(Issue.status == "active")
            .distinct()
        )

        result = await db.execute(query)
        rows = result.fetchall()

        return [
            {
                "issue_id": str(row[0]),
                "issue_name": row[1],
                "name_embedding": row[2],
            }
            for row in rows
        ]

    async def _find_best_embedding_match(
        self,
        embedding: list[float],
        candidate_issues: list[dict],
        db: AsyncSession
    ) -> dict | None:
        """후보 이슈들 중 임베딩 유사도가 가장 높은 것 찾기"""
        if not candidate_issues:
            return None

        # 후보들의 name_embedding과 Python에서 유사도 계산
        best_match = None
        best_similarity = 0.0

        for candidate in candidate_issues:
            name_emb = candidate.get("name_embedding")
            if name_emb is not None:
                # 코사인 유사도 계산
                similarity = self._cosine_similarity(embedding, list(name_emb))
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = {
                        "issue_id": candidate["issue_id"],
                        "issue_name": candidate["issue_name"],
                        "similarity": similarity,
                    }

        return best_match

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """코사인 유사도 계산"""
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def _find_high_similarity_match(
        self,
        embedding: list[float],
        db: AsyncSession
    ) -> dict | None:
        """전체 이슈 대상 높은 유사도 매칭 (alias 가능성)"""
        # 활성 이슈들 조회
        query = (
            select(Issue.id, Issue.name, Issue.name_embedding)
            .where(Issue.status == "active")
            .where(Issue.name_embedding.isnot(None))
        )
        result = await db.execute(query)
        rows = result.fetchall()

        # Python에서 유사도 계산
        best_match = None
        best_similarity = 0.0

        for row in rows:
            name_emb = row[2]
            if name_emb is not None:
                similarity = self._cosine_similarity(embedding, list(name_emb))
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = {
                        "issue_id": str(row[0]),
                        "issue_name": row[1],
                        "similarity": similarity,
                    }

        if best_match and best_match["similarity"] >= settings.EMBEDDING_HIGH_THRESHOLD:
            return best_match
        return None

    async def _create_new_issue(
        self,
        article: ArticleData,
        ner_data: NERData,
        db: AsyncSession
    ) -> tuple[Issue, dict]:
        """새 이슈 생성"""

        # 이슈 이름 생성 (who + what_summary 조합)
        who_list = ner_data.get("who", [])
        what_summary = ner_data.get("what_summary", "")
        what_type = ner_data.get("what_type")

        # what_summary가 있으면 그대로 사용 (이미 주체 정보 포함)
        if what_summary:
            issue_name = what_summary
        elif who_list:
            main_entity = who_list[0].get("name", "")
            issue_name = main_entity or article["title"][:50]
        else:
            issue_name = article["title"][:50]

        # 카테고리 추론 (이슈명 기반 키워드 오버라이드 포함)
        category = self._infer_category(what_type, issue_name)

        # 이슈 이름 임베딩 생성
        name_embedding = self.embedding_provider.embed(issue_name)

        today = datetime.now(KST).date()

        # 이슈 생성
        issue = Issue(
            name=issue_name,
            category=category,
            what_type=what_type,
            what_summary=what_summary,
            first_seen_at=today,
            last_seen_at=today,
            status="active",
            name_embedding=name_embedding,
        )
        db.add(issue)
        await db.flush()

        # Entity 생성 및 연결
        await self._create_entities(issue.id, ner_data, db)

        new_issue_info = {
            "id": str(issue.id),
            "name": issue_name,
            "category": category,
            "what_type": what_type,
        }

        return issue, new_issue_info

    def _infer_category(self, what_type: str | None, issue_name: str = "") -> str:
        """what_type과 이슈명에서 카테고리 추론

        우선순위:
        1. 이슈명에서 정치 키워드 감지 → 정치
        2. what_type 매핑
        3. 기본값 → 사회
        """
        # 정치 키워드 (당명, 직책, 기관 등)
        political_keywords = [
            # 정당
            "국민의힘", "민주당", "더불어민주당", "조국혁신당", "개혁신당",
            "새로운미래", "진보당", "녹색정의당",
            # 직책
            "대통령", "총리", "장관", "의원", "국회", "대표", "원내대표",
            "정책위의장", "비서실장", "수석", "비대위",
            # 기관
            "청와대", "대통령실", "여당", "야당", "여야",
            # 정치 활동
            "탄핵", "해임", "임명", "인사청문", "사퇴", "출마", "공천",
            "당대회", "전당대회", "윤리위",
        ]

        # 이슈명에서 정치 키워드 검색
        if issue_name:
            for keyword in political_keywords:
                if keyword in issue_name:
                    return "정치"

        # what_type 기반 매핑
        category_map = {
            "TRIAL": "정치",
            "INVESTIGATION": "사회",
            "LEGISLATION": "정치",
            "POLICY": "정치",
            "ACCIDENT": "사회",
            "DIPLOMACY": "세계",
            "ECONOMY": "경제",
            "ENTERTAINMENT": "연예",
        }
        return category_map.get(what_type, "사회")

    async def _create_entities(
        self,
        issue_id: UUID,
        ner_data: NERData,
        db: AsyncSession
    ):
        """엔티티 생성 및 이슈와 연결"""
        who_list = ner_data.get("who", [])
        where_list = ner_data.get("where", [])
        today = datetime.now(KST).date()

        # Who 엔티티
        for i, who in enumerate(who_list):
            entity = await self._get_or_create_entity(
                name=who.get("name", ""),
                entity_type=who.get("type", "person"),
                db=db
            )
            if entity:
                role = "primary" if i == 0 else "secondary"
                issue_entity = IssueEntity(
                    issue_id=issue_id,
                    entity_id=entity.id,
                    role=role,
                    first_seen_at=today,
                    last_seen_at=today,
                )
                db.add(issue_entity)

        # Where 엔티티
        for loc in where_list:
            entity = await self._get_or_create_entity(
                name=loc,
                entity_type="loc",
                db=db
            )
            if entity:
                issue_entity = IssueEntity(
                    issue_id=issue_id,
                    entity_id=entity.id,
                    role="related",
                    first_seen_at=today,
                    last_seen_at=today,
                )
                db.add(issue_entity)

    async def _get_or_create_entity(
        self,
        name: str,
        entity_type: str,
        db: AsyncSession
    ) -> Entity | None:
        """엔티티 조회 또는 생성"""
        if not name:
            return None

        # 기존 엔티티 찾기
        query = select(Entity).where(
            Entity.name == name,
            Entity.type == entity_type
        )
        result = await db.execute(query)
        entity = result.scalar_one_or_none()

        if entity:
            return entity

        # 새로 생성
        entity = Entity(
            name=name,
            type=entity_type,
            aliases=[],
        )
        db.add(entity)
        await db.flush()
        return entity

    async def _save_article(
        self,
        article: ArticleData,
        ner_data: NERData | None,
        issue_id: UUID,
        db: AsyncSession
    ) -> bool:
        """기사 저장 (중복 URL 체크 포함)

        Returns:
            True if saved, False if duplicate
        """
        # URL 정규화 및 중복 체크
        normalized_url = article["url"].split("?")[0].rstrip("/")
        existing = await db.execute(
            select(IssueArticle.id).where(IssueArticle.url == normalized_url).limit(1)
        )
        if existing.scalar_one_or_none():
            logger.debug(f"중복 URL 스킵: {normalized_url[:50]}...")
            return False

        now = datetime.now(KST)

        # NER 결과를 entities JSON으로 변환
        entities_json = {}
        if ner_data:
            entities_json = {
                "who": ner_data.get("who", []),
                "where": ner_data.get("where", []),
                "what_type": ner_data.get("what_type"),
                "what_summary": ner_data.get("what_summary"),
            }

        issue_article = IssueArticle(
            issue_id=issue_id,
            title=article["title"],
            url=normalized_url,
            description=article.get("description"),
            press=article.get("press"),
            source=article.get("source"),
            published_at=article.get("published_at"),
            collected_at=now,
            entities=entities_json,
            status="matched" if issue_id != UNASSIGNED_ISSUE_ID else "pending",
            matched_at=now if issue_id != UNASSIGNED_ISSUE_ID else None,
        )
        db.add(issue_article)

        # 기사 제목 임베딩도 저장
        if article.get("embedding"):
            embedding = IssueEmbedding(
                issue_id=issue_id,
                content_type="article_title",
                content=article["title"],
                embedding=article["embedding"],
            )
            db.add(embedding)

        return True

    async def _update_issue_dates(self, issue_id: UUID, db: AsyncSession):
        """이슈의 last_seen_at 업데이트"""
        today = datetime.now(KST).date()
        query = select(Issue).where(Issue.id == issue_id)
        result = await db.execute(query)
        issue = result.scalar_one_or_none()

        if issue:
            issue.last_seen_at = today

    async def _try_promote_with_unassigned(
        self,
        idx: int,
        article: ArticleData,
        ner_data: NERData | None,
        embedding: list[float],
        db: AsyncSession
    ) -> tuple[MatchResult, dict] | None:
        """UNASSIGNED 기사들과 비교해서 유사하면 함께 새 이슈로 승격"""
        # UNASSIGNED 기사들과 임베딩 조회
        query = (
            select(
                IssueArticle.id,
                IssueArticle.title,
                IssueArticle.entities,
                IssueEmbedding.embedding
            )
            .join(IssueEmbedding, and_(
                IssueEmbedding.issue_id == IssueArticle.issue_id,
                IssueEmbedding.content == IssueArticle.title
            ))
            .where(IssueArticle.issue_id == UNASSIGNED_ISSUE_ID)
            .where(IssueArticle.status == "pending")
            .where(IssueEmbedding.embedding.isnot(None))
            .limit(20)
        )

        result = await db.execute(query)
        rows = result.fetchall()

        # Python에서 유사도 계산하고 유사한 기사 찾기
        for row in rows:
            row_embedding = row[3]
            if row_embedding is None:
                continue
            similarity = self._cosine_similarity(embedding, list(row_embedding))
            if similarity >= settings.UNASSIGNED_SIMILARITY_THRESHOLD:
                # 유사한 UNASSIGNED 기사 발견 → 새 이슈로 승격
                similar_article_id = row[0]
                similar_title = row[1]
                similar_entities = row[2] or {}

                logger.info(
                    f"[{idx}] UNASSIGNED 승격: 유사 기사 발견 "
                    f"(sim={similarity:.2f})\n"
                    f"  현재: {article['title'][:40]}\n"
                    f"  유사: {similar_title[:40]}"
                )

                # 두 기사의 NER 정보 병합해서 새 이슈 생성
                merged_ner = self._merge_ner_data(ner_data, similar_entities)

                issue, new_issue_info = await self._create_new_issue(
                    article, merged_ner, db
                )

                # 현재 기사 저장
                await self._save_article(article, ner_data, issue.id, db)

                # 기존 UNASSIGNED 기사를 새 이슈로 이동
                await self._move_article_to_issue(
                    similar_article_id, issue.id, db
                )

                return MatchResult(
                    article_idx=idx,
                    issue_id=str(issue.id),
                    issue_name=issue.name,
                    is_new_issue=True,
                    similarity=similarity,
                ), new_issue_info

        return None

    def _merge_ner_data(
        self,
        ner_data: NERData | None,
        existing_entities: dict
    ) -> NERData:
        """두 NER 데이터 병합"""
        merged_who = []
        merged_where = []
        what_type = None
        what_summary = None

        # 기존 UNASSIGNED 기사의 NER
        if existing_entities:
            merged_who.extend(existing_entities.get("who", []))
            merged_where.extend(existing_entities.get("where", []))
            what_type = existing_entities.get("what_type")
            what_summary = existing_entities.get("what_summary")

        # 현재 기사의 NER 추가
        if ner_data:
            for who in ner_data.get("who", []):
                if who not in merged_who:
                    merged_who.append(who)
            for where in ner_data.get("where", []):
                if where not in merged_where:
                    merged_where.append(where)
            if not what_type:
                what_type = ner_data.get("what_type")
            if not what_summary:
                what_summary = ner_data.get("what_summary")

        return NERData(
            article_idx=-1,  # 병합용이므로 의미 없음
            who=merged_who[:3],  # 최대 3개
            where=merged_where[:2],  # 최대 2개
            what_type=what_type,
            what_summary=what_summary,
            validation_flags=[],
            is_valid=True,
        )

    async def _move_article_to_issue(
        self,
        article_id: UUID,
        new_issue_id: UUID,
        db: AsyncSession
    ):
        """기사를 다른 이슈로 이동"""
        now = datetime.now(KST)

        # 기사 조회 및 업데이트
        article_query = select(IssueArticle).where(IssueArticle.id == article_id)
        article_result = await db.execute(article_query)
        article = article_result.scalar_one_or_none()

        if article:
            article.issue_id = new_issue_id
            article.status = "matched"
            article.matched_at = now

            # 해당 기사의 임베딩도 이동
            embedding_query = (
                select(IssueEmbedding)
                .where(IssueEmbedding.issue_id == UNASSIGNED_ISSUE_ID)
                .where(IssueEmbedding.content == article.title)
            )
            embedding_result = await db.execute(embedding_query)
            embeddings = embedding_result.scalars().all()

            for emb in embeddings:
                emb.issue_id = new_issue_id

    async def _save_to_unassigned(
        self,
        idx: int,
        article: ArticleData,
        ner_data: NERData | None,
        db: AsyncSession
    ) -> MatchResult:
        """UNASSIGNED 이슈에 저장"""
        await self._save_article(
            article, ner_data, UNASSIGNED_ISSUE_ID, db
        )

        logger.debug(f"[{idx}] UNASSIGNED로 저장: {article['title'][:50]}")

        return MatchResult(
            article_idx=idx,
            issue_id=str(UNASSIGNED_ISSUE_ID),
            issue_name="UNASSIGNED",
            is_new_issue=False,
            similarity=0.0,
        )

    async def _fetch_naver_articles(
        self,
        issue: Issue,
        db: AsyncSession
    ) -> int:
        """새 이슈에 대해 Naver 검색으로 추가 기사 수집"""
        try:
            # 이슈 이름에서 검색 키워드 추출 (첫 번째 entity 또는 이슈 이름)
            search_query = issue.name[:30]  # 너무 길면 잘라서 검색

            # Naver 검색
            results = self.naver.search_news(search_query, display=10, sort="date")

            if not results:
                return 0

            # 기존 URL 조회 (중복 방지)
            urls = [r.url.split("?")[0].rstrip("/") for r in results]
            existing_query = select(IssueArticle.url).where(IssueArticle.url.in_(urls))
            existing_result = await db.execute(existing_query)
            existing_urls = {
                row[0].split("?")[0].rstrip("/") for row in existing_result.all()
            }

            now = datetime.now(KST)
            added_count = 0

            for news_item in results:
                normalized_url = news_item.url.split("?")[0].rstrip("/")
                if normalized_url in existing_urls:
                    continue

                # 기사 저장 (정규화된 URL 사용)
                article = IssueArticle(
                    issue_id=issue.id,
                    title=news_item.title,
                    url=normalized_url,
                    description=news_item.description,
                    press=news_item.press or None,
                    source="naver",
                    published_at=news_item.published_at,
                    collected_at=now,
                    entities={},
                    status="matched",
                    matched_at=now,
                )
                db.add(article)
                added_count += 1
                existing_urls.add(normalized_url)  # 같은 배치 내 중복 방지

            if added_count > 0:
                await db.flush()

            return added_count

        except Exception as e:
            logger.warning(f"Naver 추가 수집 실패 ({issue.name}): {e}")
            return 0


# 싱글톤 인스턴스
match_node = MatchNode()
