"""Notification router."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Notification, User
from shared.database.base import get_db

from ..dependencies import get_current_user
from ..schemas.notifications import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    NotificationResponse,
    NotificationType,
    UnreadCountResponse,
)
from ..services.notification_manager import notification_manager

logger = logging.getLogger(__name__)

# Security scheme for Swagger UI
security = HTTPBearer()

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    type: Optional[NotificationType] = Query(None, description="Filter by type"),
    credentials: HTTPAuthorizationCredentials = Security(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user notifications with pagination and filters."""
    notifications, total_count = await notification_manager.get_user_notifications(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        is_read=is_read,
        notification_type=type,
    )

    # Get unread count
    unread_count = await notification_manager.get_unread_count(db, current_user.id)

    # Build response with actor info
    notification_responses = []
    for notif in notifications:
        # Get actor info if present
        actor_username = None
        actor_display_name = None
        if notif.actor_id:
            stmt = select(User).where(User.id == notif.actor_id)
            result = await db.execute(stmt)
            actor = result.scalar_one_or_none()
            if actor:
                actor_username = actor.username
                actor_display_name = actor.display_name

        notification_responses.append(
            NotificationResponse(
                id=notif.id,
                user_id=notif.user_id,
                type=NotificationType(notif.type),
                title=notif.title,
                message=notif.message,
                reference_id=notif.reference_id,
                reference_type=notif.reference_type,
                is_read=notif.is_read,
                created_at=notif.created_at,
                read_at=notif.read_at,
                actor_username=actor_username,
                actor_display_name=actor_display_name,
            )
        )

    return NotificationListResponse(
        notifications=notification_responses,
        total_count=total_count,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
    )


@router.get("/unread/count", response_model=UnreadCountResponse)
async def get_unread_count(
    credentials: HTTPAuthorizationCredentials = Security(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get unread notification count."""
    count = await notification_manager.get_unread_count(db, current_user.id)
    return UnreadCountResponse(count=count)


@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    credentials: HTTPAuthorizationCredentials = Security(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    notification = await notification_manager.mark_as_read(
        db, notification_id, current_user.id
    )

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Get actor info
    actor_username = None
    actor_display_name = None
    if notification.actor_id:
        stmt = select(User).where(User.id == notification.actor_id)
        result = await db.execute(stmt)
        actor = result.scalar_one_or_none()
        if actor:
            actor_username = actor.username
            actor_display_name = actor.display_name

    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        type=NotificationType(notification.type),
        title=notification.title,
        message=notification.message,
        reference_id=notification.reference_id,
        reference_type=notification.reference_type,
        is_read=notification.is_read,
        created_at=notification.created_at,
        read_at=notification.read_at,
        actor_username=actor_username,
        actor_display_name=actor_display_name,
    )


@router.put("/read-all", response_model=MarkAllReadResponse)
async def mark_all_read(
    credentials: HTTPAuthorizationCredentials = Security(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read."""
    count = await notification_manager.mark_all_as_read(db, current_user.id)
    return MarkAllReadResponse(marked_read=count)


@router.delete("/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: UUID,
    credentials: HTTPAuthorizationCredentials = Security(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification."""
    deleted = await notification_manager.delete_notification(
        db, notification_id, current_user.id
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Notification not found")

    return None


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(
    credentials: HTTPAuthorizationCredentials = Security(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user notification preferences."""
    prefs = await notification_manager.get_user_preferences(db, current_user.id)

    return NotificationPreferencesResponse(
        user_id=prefs.user_id,
        mentions=prefs.mentions,
        reactions=prefs.reactions,
        replies=prefs.replies,
        direct_messages=prefs.direct_messages,
        channel_updates=prefs.channel_updates,
        updated_at=prefs.updated_at,
    )


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_preferences(
    preferences: NotificationPreferencesUpdate,
    credentials: HTTPAuthorizationCredentials = Security(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user notification preferences."""
    prefs = await notification_manager.update_user_preferences(
        db=db,
        user_id=current_user.id,
        mentions=preferences.mentions,
        reactions=preferences.reactions,
        replies=preferences.replies,
        direct_messages=preferences.direct_messages,
        channel_updates=preferences.channel_updates,
    )

    return NotificationPreferencesResponse(
        user_id=prefs.user_id,
        mentions=prefs.mentions,
        reactions=prefs.reactions,
        replies=prefs.replies,
        direct_messages=prefs.direct_messages,
        channel_updates=prefs.channel_updates,
        updated_at=prefs.updated_at,
    )
