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
