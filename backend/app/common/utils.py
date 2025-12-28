"""공통 유틸리티"""
import time
import hashlib
import functools
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Callable, TypeVar, Any
from datetime import datetime, timezone, timedelta

# 한국 시간대 (UTC+9)
KST = timezone(timedelta(hours=9))

T = TypeVar('T')


def retry(max_attempts: int = 3, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """재시도 데코레이터

    Args:
        max_attempts: 최대 시도 횟수
        backoff: 재시도 간격 배수 (1초, 2초, 4초...)
        exceptions: 재시도할 예외 타입들
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = backoff ** attempt
                        print(f"[RETRY] {func.__name__} 실패 (시도 {attempt + 1}/{max_attempts}), {wait_time:.1f}초 후 재시도: {e}")
                        time.sleep(wait_time)
                    else:
                        print(f"[RETRY] {func.__name__} 최종 실패 ({max_attempts}회 시도): {e}")
            raise last_exception

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            import asyncio
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = backoff ** attempt
                        print(f"[RETRY] {func.__name__} 실패 (시도 {attempt + 1}/{max_attempts}), {wait_time:.1f}초 후 재시도: {e}")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"[RETRY] {func.__name__} 최종 실패 ({max_attempts}회 시도): {e}")
            raise last_exception

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


class ArticleDeduplicator:
    """기사 중복 제거기"""

    def __init__(self):
        self.seen_urls: set[str] = set()
        self.seen_hashes: set[str] = set()

    def _hash_content(self, title: str, description: str = "") -> str:
        """제목+내용으로 해시 생성"""
        content = f"{title}:{description}".lower().strip()
        return hashlib.md5(content.encode()).hexdigest()

    def is_duplicate(self, url: str, title: str, description: str = "") -> bool:
        """중복 여부 확인"""
        # URL 중복 체크
        if url in self.seen_urls:
            return True

        # 내용 해시 중복 체크 (URL 다르지만 내용 같은 경우)
        content_hash = self._hash_content(title, description)
        if content_hash in self.seen_hashes:
            return True

        return False

    def add(self, url: str, title: str, description: str = "") -> None:
        """기사 추가"""
        self.seen_urls.add(url)
        content_hash = self._hash_content(title, description)
        self.seen_hashes.add(content_hash)

    def filter_articles(self, articles: list[dict]) -> list[dict]:
        """중복 제거된 기사 리스트 반환"""
        unique = []
        for article in articles:
            url = article.get("url", "")
            title = article.get("title", "")
            description = article.get("description", "")

            if not self.is_duplicate(url, title, description):
                self.add(url, title, description)
                unique.append(article)

        return unique

    def reset(self) -> None:
        """상태 초기화"""
        self.seen_urls.clear()
        self.seen_hashes.clear()


class PipelineResult:
    """파이프라인 실행 결과"""

    def __init__(self):
        self.successful: list[Any] = []
        self.failed: list[tuple[Any, Exception]] = []

    @property
    def partial(self) -> bool:
        """부분 성공 여부"""
        return len(self.successful) > 0 and len(self.failed) > 0

    @property
    def total(self) -> int:
        return len(self.successful) + len(self.failed)

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return len(self.successful) / self.total

    def add_success(self, item: Any) -> None:
        self.successful.append(item)

    def add_failure(self, item: Any, error: Exception) -> None:
        self.failed.append((item, error))

    def summary(self) -> str:
        return f"성공: {len(self.successful)}, 실패: {len(self.failed)}, 성공률: {self.success_rate:.1%}"


class EmailService:
    """Gmail SMTP 이메일 서비스"""

    def __init__(self, gmail_user: str, gmail_app_password: str):
        self.gmail_user = gmail_user
        self.gmail_app_password = gmail_app_password
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def send_batch_complete(
        self,
        recipient: str,
        issues_count: int,
        duration_seconds: float,
        success_count: int = 0,
        fail_count: int = 0
    ) -> bool:
        """배치 완료 알림 이메일 발송"""
        if not self.gmail_user or not self.gmail_app_password:
            print("[EMAIL] Gmail 설정 없음, 이메일 발송 스킵")
            return False

        try:
            now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
            duration_min = duration_seconds / 60

            subject = f"[DSTILL] 배치 완료 - {issues_count}개 이슈 수집됨"

            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>🎯 DSTILL 배치 완료</h2>
                <table style="border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>완료 시간</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{now}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>수집된 이슈</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{issues_count}개</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>성공/실패</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{success_count}개 / {fail_count}개</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>소요 시간</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{duration_min:.1f}분</td>
                    </tr>
                </table>
                <p style="color: #666; font-size: 12px;">이 메일은 DSTILL 자동 알림입니다.</p>
            </body>
            </html>
            """

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.gmail_user
            msg["To"] = recipient
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.gmail_user, self.gmail_app_password)
                server.sendmail(self.gmail_user, recipient, msg.as_string())

            print(f"[EMAIL] 배치 완료 알림 발송: {recipient}")
            return True

        except Exception as e:
            print(f"[EMAIL] 발송 실패: {e}")
            return False

    def send_issues_digest(
        self,
        recipient: str,
        issues: list[dict],
        categories: list[str] | None = None,
        magic_link_url: str | None = None,
        batch_time: datetime | None = None
    ) -> bool:
        """이슈 다이제스트 이메일 발송

        Args:
            recipient: 수신자 이메일
            issues: 이슈 목록 [{name, category, summary, article_count}, ...]
            categories: 사용자가 선택한 카테고리 (없으면 전체)
            magic_link_url: 자동 로그인 매직 링크 URL
            batch_time: 배치 실행 시간 (없으면 현재 시간)
        """
        if not self.gmail_user or not self.gmail_app_password:
            print("[EMAIL] Gmail 설정 없음, 이메일 발송 스킵")
            return False

        if not issues:
            print("[EMAIL] 발송할 이슈 없음")
            return False

        try:
            # 배치 시간 기준 (없으면 현재 시간), UTC → KST 변환
            reference_time = batch_time or datetime.now(KST)
            if reference_time.tzinfo is not None:
                # UTC 등 다른 시간대면 KST로 변환
                reference_time = reference_time.astimezone(KST)
            else:
                reference_time = reference_time.replace(tzinfo=KST)
            time_str = reference_time.strftime("%Y-%m-%d %H:%M")

            category_text = ", ".join(categories) if categories else "전체"
            link_url = magic_link_url or "https://kimmykim.dev"

            subject = f"[DSTILL] 오늘의 이슈 {len(issues)}개 - {time_str}"

            # 이슈 목록 HTML 생성
            issues_html = ""
            for issue in issues:
                category_badge = f'<span style="background: #f3f4f6; padding: 2px 8px; border-radius: 12px; font-size: 12px; color: #6b7280;">{issue.get("category", "기타")}</span>'
                summary = issue.get("summary", "")[:150] + "..." if issue.get("summary") and len(issue.get("summary", "")) > 150 else issue.get("summary", "-")

                issues_html += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 12px 8px; vertical-align: top;">
                        <div style="font-weight: 600; color: #1f2937; margin-bottom: 4px;">{issue['name']}</div>
                        <div style="font-size: 13px; color: #6b7280; margin-bottom: 4px;">{summary}</div>
                        <div>{category_badge} <span style="color: #9ca3af; font-size: 12px;">기사 {issue.get('article_count', 0)}개</span></div>
                    </td>
                </tr>
                """

            html_body = f"""
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; background: #f9fafb;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h2 style="color: #1b1b32; margin-bottom: 8px;">📰 오늘의 이슈</h2>
                    <p style="color: #6b7280; margin-bottom: 20px; font-size: 14px;">
                        {time_str} 기준 | 카테고리: {category_text}
                    </p>

                    <table style="width: 100%; border-collapse: collapse;">
                        {issues_html}
                    </table>

                    <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee;">
                        <a href="{link_url}" style="display: inline-block; background: #f59e0b; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 500;">
                            DSTILL에서 자세히 보기
                        </a>
                        <p style="color: #9ca3af; font-size: 11px; margin-top: 8px;">
                            이 링크는 10분간 유효합니다.
                        </p>
                    </div>

                    <p style="color: #9ca3af; font-size: 12px; margin-top: 20px;">
                        이 메일은 DSTILL 자동 알림입니다. 설정에서 알림을 변경할 수 있습니다.
                    </p>
                </div>
            </body>
            </html>
            """

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.gmail_user
            msg["To"] = recipient
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.gmail_user, self.gmail_app_password)
                server.sendmail(self.gmail_user, recipient, msg.as_string())

            print(f"[EMAIL] 이슈 다이제스트 발송: {recipient} ({len(issues)}개 이슈)")
            return True

        except Exception as e:
            print(f"[EMAIL] 발송 실패: {e}")
            return False

    def send_followed_issues_update(
        self,
        recipient: str,
        issues: list[dict],
        magic_link_url: str | None = None,
        batch_time: datetime | None = None
    ) -> bool:
        """팔로우 이슈 업데이트 이메일 발송

        Args:
            recipient: 수신자 이메일
            issues: 이슈 목록 [{name, category, summary, article_count, issue_id}, ...]
            magic_link_url: 자동 로그인 매직 링크 URL
            batch_time: 배치 실행 시간 (없으면 현재 시간)
        """
        if not self.gmail_user or not self.gmail_app_password:
            print("[EMAIL] Gmail 설정 없음, 이메일 발송 스킵")
            return False

        if not issues:
            print("[EMAIL] 발송할 팔로우 이슈 없음")
            return False

        try:
            # 배치 시간 기준 (없으면 현재 시간), UTC → KST 변환
            reference_time = batch_time or datetime.now(KST)
            if reference_time.tzinfo is not None:
                # UTC 등 다른 시간대면 KST로 변환
                reference_time = reference_time.astimezone(KST)
            else:
                reference_time = reference_time.replace(tzinfo=KST)
            time_str = reference_time.strftime("%Y-%m-%d %H:%M")

            base_url = magic_link_url.split("?")[0].rsplit("/", 1)[0] if magic_link_url else "https://kimmykim.dev"
            link_url = magic_link_url or "https://kimmykim.dev"

            subject = f"[DSTILL] 팔로우 이슈 업데이트 {len(issues)}건 - {time_str}"

            # 이슈 목록 HTML 생성
            issues_html = ""
            for issue in issues:
                category_badge = f'<span style="background: #fef3c7; padding: 2px 8px; border-radius: 12px; font-size: 12px; color: #d97706;">{issue.get("category", "기타")}</span>'
                summary = issue.get("summary", "")[:150] + "..." if issue.get("summary") and len(issue.get("summary", "")) > 150 else issue.get("summary", "-")

                issues_html += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 12px 8px; vertical-align: top;">
                        <div style="font-weight: 600; color: #1f2937; margin-bottom: 4px;">
                            🔔 {issue['name']}
                        </div>
                        <div style="font-size: 13px; color: #6b7280; margin-bottom: 4px;">{summary}</div>
                        <div>{category_badge} <span style="color: #9ca3af; font-size: 12px;">기사 {issue.get('article_count', 0)}개</span></div>
                    </td>
                </tr>
                """

            html_body = f"""
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; background: #f9fafb;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h2 style="color: #1b1b32; margin-bottom: 8px;">🔔 팔로우 이슈 업데이트</h2>
                    <p style="color: #6b7280; margin-bottom: 20px; font-size: 14px;">
                        {time_str} 기준 | 팔로우 중인 이슈에 새 소식이 있습니다
                    </p>

                    <table style="width: 100%; border-collapse: collapse;">
                        {issues_html}
                    </table>

                    <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee;">
                        <a href="{link_url}" style="display: inline-block; background: #f59e0b; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 500;">
                            DSTILL에서 자세히 보기
                        </a>
                        <p style="color: #9ca3af; font-size: 11px; margin-top: 8px;">
                            이 링크는 10분간 유효합니다.
                        </p>
                    </div>

                    <p style="color: #9ca3af; font-size: 12px; margin-top: 20px;">
                        이 메일은 팔로우 중인 이슈의 업데이트 알림입니다. 이슈 상세 페이지에서 팔로우를 해제할 수 있습니다.
                    </p>
                </div>
            </body>
            </html>
            """

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.gmail_user
            msg["To"] = recipient
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.gmail_user, self.gmail_app_password)
                server.sendmail(self.gmail_user, recipient, msg.as_string())

            print(f"[EMAIL] 팔로우 이슈 업데이트 발송: {recipient} ({len(issues)}개 이슈)")
            return True

        except Exception as e:
            print(f"[EMAIL] 발송 실패: {e}")
            return False

    def send_daily_digest(
        self,
        recipient: str,
        digest_date: str,
        total_issues: int,
        new_issues_count: int,
        total_articles: int,
        categories: list[dict],
        base_url: str = "https://kimmykim.dev"
    ) -> bool:
        """데일리 다이제스트 이메일 발송

        Args:
            recipient: 수신자 이메일
            digest_date: 다이제스트 날짜 (YYYY-MM-DD)
            total_issues: 총 이슈 수
            new_issues_count: 신규 이슈 수
            total_articles: 총 기사 수
            categories: 카테고리별 이슈 [{category, issues: [{name, article_count, is_new}], total_articles}]
            base_url: 사이트 기본 URL
        """
        if not self.gmail_user or not self.gmail_app_password:
            print("[EMAIL] Gmail 설정 없음, 이메일 발송 스킵")
            return False

        try:
            # 날짜 포맷
            from datetime import datetime
            date_obj = datetime.strptime(digest_date, "%Y-%m-%d")
            date_display = date_obj.strftime("%Y년 %m월 %d일")

            subject = f"[DSTILL] {date_display} 브리핑 - {total_issues}개 이슈"

            # 카테고리별 이슈 HTML 생성
            categories_html = ""
            for cat in categories:
                issues_list = ""
                for issue in cat["issues"][:5]:  # 카테고리당 최대 5개
                    new_badge = '<span style="background: #fee2e2; color: #dc2626; padding: 1px 6px; border-radius: 10px; font-size: 10px; margin-left: 4px;">NEW</span>' if issue.get("is_new") else ""
                    issues_list += f"""
                    <div style="padding: 8px 0; border-bottom: 1px solid #f3f4f6;">
                        <span style="font-weight: 500; color: #1f2937;">{issue['name']}</span>{new_badge}
                        <span style="color: #9ca3af; font-size: 12px; margin-left: 8px;">기사 {issue.get('article_count', 0)}개</span>
                    </div>
                    """

                if len(cat["issues"]) > 5:
                    issues_list += f'<div style="padding: 8px 0; color: #6b7280; font-size: 12px;">외 {len(cat["issues"]) - 5}개 이슈...</div>'

                categories_html += f"""
                <div style="margin-bottom: 20px;">
                    <div style="background: #fef3c7; padding: 6px 12px; border-radius: 6px; display: inline-block; margin-bottom: 8px;">
                        <span style="font-weight: 600; color: #92400e;">{cat['category']}</span>
                        <span style="color: #d97706; font-size: 12px; margin-left: 8px;">{len(cat['issues'])}개 이슈</span>
                    </div>
                    {issues_list}
                </div>
                """

            html_body = f"""
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; background: #f9fafb;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <h2 style="color: #1b1b32; margin-bottom: 4px;">📰 {date_display} 브리핑</h2>
                    <p style="color: #6b7280; margin-top: 0; margin-bottom: 20px;">어제 있었던 주요 이슈를 한눈에 확인하세요</p>

                    <!-- 통계 요약 -->
                    <div style="display: flex; gap: 12px; margin-bottom: 24px;">
                        <div style="flex: 1; background: #f9fafb; padding: 12px; border-radius: 8px; text-align: center;">
                            <div style="font-size: 24px; font-weight: 700; color: #1f2937;">{total_issues}</div>
                            <div style="font-size: 12px; color: #6b7280;">총 이슈</div>
                        </div>
                        <div style="flex: 1; background: #fef2f2; padding: 12px; border-radius: 8px; text-align: center;">
                            <div style="font-size: 24px; font-weight: 700; color: #dc2626;">{new_issues_count}</div>
                            <div style="font-size: 12px; color: #6b7280;">신규 이슈</div>
                        </div>
                        <div style="flex: 1; background: #fffbeb; padding: 12px; border-radius: 8px; text-align: center;">
                            <div style="font-size: 24px; font-weight: 700; color: #d97706;">{total_articles}</div>
                            <div style="font-size: 12px; color: #6b7280;">총 기사</div>
                        </div>
                    </div>

                    <!-- 카테고리별 이슈 -->
                    {categories_html}

                    <!-- CTA 버튼 -->
                    <div style="text-align: center; margin-top: 24px;">
                        <a href="{base_url}/digest/{digest_date}" style="display: inline-block; background: #f59e0b; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
                            전체 브리핑 보기 →
                        </a>
                    </div>

                    <p style="color: #9ca3af; font-size: 12px; margin-top: 24px; text-align: center;">
                        이 메일은 DSTILL 데일리 다이제스트입니다.
                    </p>
                </div>
            </body>
            </html>
            """

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.gmail_user
            msg["To"] = recipient
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.gmail_user, self.gmail_app_password)
                server.sendmail(self.gmail_user, recipient, msg.as_string())

            print(f"[EMAIL] 데일리 다이제스트 발송: {recipient} ({digest_date})")
            return True

        except Exception as e:
            print(f"[EMAIL] 다이제스트 발송 실패: {e}")
            return False
