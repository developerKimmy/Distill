"""모든 모델을 올바른 순서로 import

SQLAlchemy relationship 해결을 위해 모든 모델을
의존성 순서대로 import합니다.
"""

# 1. Base (먼저)
from app.core.base import Base  # noqa: F401

# 2. User 모델 (다른 모델들이 참조)
from app.auth.models import User  # noqa: F401

# 3. User 설정
from app.settings.models import UserSettings  # noqa: F401

# 4. 이슈 관련 모델
from app.issues.models import (  # noqa: F401
    Entity,
    Issue,
    IssueEntity,
    IssueArticle,
    IssueContent,
    IssueEmbedding,
    IssueKeyword,
    IssueInsight,
    IssueFollow,
    DailyDigest,
)

# 5. 알림 모델
from app.notifications.models import Notification, AgentRun  # noqa: F401
