"""매직 링크 토큰 서비스"""
from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt

from app.core.config import settings


# 매직 링크 토큰 유효 시간 (10분)
MAGIC_LINK_EXPIRE_MINUTES = 10


def create_magic_token(user_id: UUID) -> str:
    """매직 링크용 단기 토큰 생성"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "type": "magic_link",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def verify_magic_token(token: str) -> UUID | None:
    """매직 링크 토큰 검증 및 user_id 반환"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        # 토큰 타입 확인
        if payload.get("type") != "magic_link":
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        return UUID(user_id)

    except jwt.ExpiredSignatureError:
        print("[MAGIC_LINK] Token expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"[MAGIC_LINK] Invalid token: {e}")
        return None


def get_magic_link_url(user_id: UUID, base_url: str = "https://kimmykim.dev") -> str:
    """매직 링크 URL 생성"""
    token = create_magic_token(user_id)
    return f"{base_url}/auth/magic?token={token}"
