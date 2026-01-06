"""기존 이슈의 카테고리를 키워드 기반으로 재분류

사용법:
    PYTHONPATH=. python3 scripts/fix_issue_categories.py
"""
import asyncio
from sqlalchemy import select
# 모든 모델을 올바른 순서로 로드
import app.core.models  # noqa: F401
from app.core.database import create_async_session_factory
from app.issues.models import Issue

# 정치 키워드
POLITICAL_KEYWORDS = [
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


def should_be_political(issue_name: str) -> bool:
    """이슈명에 정치 키워드가 있는지 확인"""
    for keyword in POLITICAL_KEYWORDS:
        if keyword in issue_name:
            return True
    return False


async def fix_categories():
    AsyncSession = create_async_session_factory()

    async with AsyncSession() as db:
        # 정치가 아닌 이슈들 조회
        stmt = select(Issue).where(Issue.category != "정치")
        result = await db.execute(stmt)
        issues = list(result.scalars().all())

        fixed_count = 0
        for issue in issues:
            if should_be_political(issue.name):
                old_category = issue.category
                issue.category = "정치"
                fixed_count += 1
                print(f"[FIX] '{issue.name}': {old_category} → 정치")

        if fixed_count > 0:
            await db.commit()
            print(f"\n총 {fixed_count}개 이슈 카테고리 수정 완료")
        else:
            print("수정할 이슈 없음")


if __name__ == "__main__":
    asyncio.run(fix_categories())
