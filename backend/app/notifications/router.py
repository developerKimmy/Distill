"""Notification Router"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_async_session
from app.notifications.models import Notification
from app.notifications.schemas import (
    NotificationResponse,
    NotificationListResponse,
    UnreadCountResponse,
)
from app.auth.models import User
from app.auth.router import fastapi_users
from app.issues.models import Issue

router = APIRouter(prefix="/notifications", tags=["notifications"])

current_active_user = fastapi_users.current_user(active=True)


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False, description="읽지 않은 알림만"),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """알림 목록 조회"""
    # 기본 쿼리
    base_query = select(Notification).where(Notification.user_id == user.id)

    if unread_only:
        base_query = base_query.where(Notification.is_read == False)

    # 전체 개수
    count_query = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # 읽지 않은 개수
    unread_query = select(func.count()).where(
        Notification.user_id == user.id,
        Notification.is_read == False,
    )
    unread_count = (await db.execute(unread_query)).scalar() or 0

    # 페이징된 알림 목록
    offset = (page - 1) * size
    notifications_query = (
        base_query
        .options(joinedload(Notification.issue))
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(notifications_query)
    notifications = list(result.scalars().all())

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=n.id,
                type=n.type,
                title=n.title,
                message=n.message,
                issue_id=n.issue_id,
                is_read=n.is_read,
                created_at=n.created_at,
                issue_name=n.issue.name if n.issue else None,
                issue_category=n.issue.category if n.issue else None,
            )
            for n in notifications
        ],
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """읽지 않은 알림 개수 조회"""
    query = select(func.count()).where(
        Notification.user_id == user.id,
        Notification.is_read == False,
    )
    count = (await db.execute(query)).scalar() or 0

    return UnreadCountResponse(count=count)


@router.put("/{notification_id}/read")
async def mark_as_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """알림 읽음 처리"""
    # 알림 조회
    query = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")

    # 읽음 처리
    notification.is_read = True
    await db.commit()

    return {"success": True}


@router.put("/read-all")
async def mark_all_as_read(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """모든 알림 읽음 처리"""
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    await db.execute(stmt)
    await db.commit()

    return {"success": True}
