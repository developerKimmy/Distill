"""알림 관련 순수 함수들"""
from datetime import datetime, timezone, timedelta
from uuid import UUID
from dataclasses import dataclass
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.batch.models import BatchRun
from app.settings.models import UserSettings
from app.auth.models import User
from app.issues.models import Issue, IssueDailySnapshot, IssueFollow
from app.common.utils import EmailService
from app.auth.magic_link import get_magic_link_url
from app.core.config import settings

KST = timezone(timedelta(hours=9))


@dataclass
class NotificationResult:
    """알림 결과"""
    sent_count: int
    message: str
    batch_run_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "sent_count": self.sent_count,
            "message": self.message,
            "batch_run_id": self.batch_run_id
        }


# ============ 시간 관련 함수 ============

def get_check_times(batch_time: str | None, now: datetime) -> list[str]:
    """알림 체크 시간 목록 반환"""
    if batch_time:
        return [batch_time]

    current_time = now.strftime("%H:%M")
    minute = now.minute
    times = [current_time]

    if minute == 5:
        times.append(f"{now.hour:02d}:00")
    elif minute == 35:
        times.append(f"{now.hour:02d}:30")

    return times


def is_today(dt: datetime, reference: datetime) -> bool:
    """주어진 시간이 오늘인지 확인 (KST 기준)"""
    dt_kst = dt.astimezone(KST)
    ref_kst = reference.astimezone(KST) if reference.tzinfo else reference.replace(tzinfo=KST)
    return dt_kst.date() == ref_kst.date()


# ============ 배치 조회 함수 ============

def get_latest_completed_batch(db: Session) -> BatchRun | None:
    """최신 완료 배치 조회"""
    return db.execute(
        select(BatchRun)
        .where(BatchRun.status == "completed")
        .order_by(BatchRun.completed_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_batch_by_id(db: Session, batch_run_id: str) -> BatchRun | None:
    """ID로 배치 조회"""
    return db.execute(
        select(BatchRun).where(BatchRun.id == UUID(batch_run_id))
    ).scalar_one_or_none()


def is_batch_already_notified(batch_run: BatchRun) -> bool:
    """배치 알림이 이미 전송됐는지 확인"""
    return batch_run.notification_sent_at is not None


def mark_batch_notified(db: Session, batch_run: BatchRun) -> None:
    """배치 알림 전송 완료 표시"""
    batch_run.notification_sent_at = datetime.now(KST)
    db.commit()


# ============ 사용자 조회 함수 ============

def get_users_for_times(db: Session, check_times: list[str]) -> list[User]:
    """특정 시간에 알림 받을 사용자 조회"""
    time_conditions = [
        UserSettings.notification_times.contains(t) for t in check_times
    ]
    return db.execute(
        select(User)
        .join(UserSettings)
        .where(
            UserSettings.email_notifications_enabled == True,
            or_(*time_conditions)
        )
    ).scalars().all()


def get_user_settings(db: Session, user_id: UUID) -> UserSettings | None:
    """사용자 설정 조회"""
    return db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    ).scalar_one_or_none()


def get_user_categories(user_settings: UserSettings | None) -> list[str]:
    """사용자 카테고리 필터 파싱"""
    if user_settings and user_settings.category_filter:
        return user_settings.category_filter.split(",")
    return []


# ============ 이슈 조회 함수 ============

def get_batch_issues(
    db: Session,
    batch_run_id: UUID,
    categories: list[str] | None = None
) -> list[dict]:
    """배치의 이슈 목록 조회"""
    stmt = (
        select(Issue, IssueDailySnapshot)
        .join(IssueDailySnapshot, Issue.id == IssueDailySnapshot.issue_id)
        .where(IssueDailySnapshot.batch_run_id == batch_run_id)
    )

    if categories:
        stmt = stmt.where(Issue.category.in_(categories))

    stmt = stmt.order_by(IssueDailySnapshot.article_count.desc())
    rows = db.execute(stmt).all()

    return [
        {
            "name": issue.name,
            "category": issue.category,
            "summary": snapshot.summary,
            "article_count": snapshot.article_count,
        }
        for issue, snapshot in rows
    ]


def get_followed_issues_by_batch(
    db: Session,
    batch_run_id: UUID
) -> dict[str, tuple[User, list[dict]]]:
    """배치에서 업데이트된 팔로우 이슈를 사용자별로 그룹핑"""
    stmt = (
        select(User, Issue, IssueDailySnapshot)
        .join(IssueFollow, User.id == IssueFollow.user_id)
        .join(Issue, IssueFollow.issue_id == Issue.id)
        .join(IssueDailySnapshot, Issue.id == IssueDailySnapshot.issue_id)
        .where(IssueDailySnapshot.batch_run_id == batch_run_id)
        .order_by(User.id, IssueDailySnapshot.article_count.desc())
    )

    rows = db.execute(stmt).all()

    user_issues: dict[str, tuple[User, list[dict]]] = {}

    for user, issue, snapshot in rows:
        user_id = str(user.id)
        if user_id not in user_issues:
            user_issues[user_id] = (user, [])

        user_issues[user_id][1].append({
            "name": issue.name,
            "category": issue.category,
            "summary": snapshot.summary,
            "article_count": snapshot.article_count,
            "issue_id": str(issue.id),
        })

    return user_issues


# ============ 이메일 발송 함수 ============

def create_email_service() -> EmailService | None:
    """이메일 서비스 생성"""
    if settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD:
        return EmailService(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
    return None


def send_digest_email(
    email_service: EmailService,
    user: User,
    issues: list[dict],
    categories: list[str] | None,
    batch_completed_at: datetime
) -> bool:
    """다이제스트 이메일 발송"""
    magic_url = get_magic_link_url(user.id)
    return email_service.send_issues_digest(
        recipient=user.email,
        issues=issues,
        categories=categories if categories else None,
        magic_link_url=magic_url,
        batch_time=batch_completed_at
    )


def send_followed_email(
    email_service: EmailService,
    user: User,
    issues: list[dict],
    batch_completed_at: datetime
) -> bool:
    """팔로우 이슈 이메일 발송"""
    magic_url = get_magic_link_url(user.id)
    return email_service.send_followed_issues_update(
        recipient=user.email,
        issues=issues,
        magic_link_url=magic_url,
        batch_time=batch_completed_at
    )


# ============ 메인 알림 로직 ============

def send_digest_notifications(db: Session, batch_time: str | None = None) -> NotificationResult:
    """카테고리 다이제스트 알림 발송"""
    now = datetime.now(KST)
    check_times = get_check_times(batch_time, now)

    # 배치 조회 및 검증
    batch_run = get_latest_completed_batch(db)
    if not batch_run:
        return NotificationResult(0, "No completed batch found")

    if is_batch_already_notified(batch_run):
        return NotificationResult(0, "Already sent", str(batch_run.id))

    if not is_today(batch_run.completed_at, now):
        return NotificationResult(0, "No batch from today")

    # 사용자 조회
    users = get_users_for_times(db, check_times)
    if not users:
        return NotificationResult(0, "No users to notify")

    # 이메일 서비스 생성
    email_service = create_email_service()
    if not email_service:
        return NotificationResult(0, "Gmail not configured")

    # 각 사용자에게 발송
    sent_count = 0
    for user in users:
        user_settings = get_user_settings(db, user.id)
        categories = get_user_categories(user_settings)
        issues = get_batch_issues(db, batch_run.id, categories or None)

        if issues and send_digest_email(
            email_service, user, issues, categories, batch_run.completed_at
        ):
            sent_count += 1

    # 알림 완료 표시
    if sent_count > 0:
        mark_batch_notified(db, batch_run)

    return NotificationResult(sent_count, "OK", str(batch_run.id))


def send_followed_notifications(db: Session, batch_run_id: str) -> NotificationResult:
    """팔로우 이슈 알림 발송"""
    batch_run = get_batch_by_id(db, batch_run_id)
    if not batch_run:
        return NotificationResult(0, "Batch not found")

    # 사용자별 팔로우 이슈 조회
    user_issues = get_followed_issues_by_batch(db, batch_run.id)
    if not user_issues:
        return NotificationResult(0, "No followed issues with updates")

    # 이메일 서비스 생성
    email_service = create_email_service()
    if not email_service:
        return NotificationResult(0, "Gmail not configured")

    # 각 사용자에게 발송
    sent_count = 0
    for user_id, (user, issues) in user_issues.items():
        if send_followed_email(email_service, user, issues, batch_run.completed_at):
            sent_count += 1

    return NotificationResult(sent_count, "OK", batch_run_id)
