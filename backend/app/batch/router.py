from fastapi import APIRouter, Depends, Header, HTTPException
from typing import Optional

from app.core.database import get_async_session
from app.core.config import settings
from app.batch.schemas import BatchTaskResponse
from app.auth.models import User
from app.auth.router import current_active_user


router = APIRouter(prefix="/batch", tags=["batch"])


def verify_cron_secret(x_cron_secret: Optional[str] = Header(None)):
    """Cron job 요청 검증 (선택적)"""
    cron_secret = getattr(settings, 'CRON_SECRET', None)
    if cron_secret and x_cron_secret != cron_secret:
        raise HTTPException(status_code=403, detail="Invalid cron secret")
    return True

@router.post("/agent/run", response_model=BatchTaskResponse)
async def run_agent_cron(
    _: bool = Depends(verify_cron_secret)
):
    """Agent 실행 (테스트/Cron용, 인증 불필요)"""
    from app.tasks.agent import run_agent_cycle

    task = run_agent_cycle.delay()

    return BatchTaskResponse(
        task_id=task.id,
        status="queued"
    )
