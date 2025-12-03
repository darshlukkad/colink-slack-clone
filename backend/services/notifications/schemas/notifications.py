"""Notification schemas."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationType(str, Enum):
    """Notification types."""

    MENTION = "mention"
    REACTION = "reaction"
    REPLY = "reply"
    DIRECT_MESSAGE = "direct_message"
    CHANNEL_INVITE = "channel_invite"
    SYSTEM = "system"


class NotificationPreferencesUpdate(BaseModel):
    """Update notification preferences."""

    mentions: Optional[bool] = None
    reactions: Optional[bool] = None
    replies: Optional[bool] = None
    direct_messages: Optional[bool] = None
    channel_updates: Optional[bool] = None


class NotificationPreferencesResponse(BaseModel):
    """Notification preferences response."""

    user_id: UUID
    mentions: bool
    reactions: bool
    replies: bool
    direct_messages: bool
    channel_updates: bool
    updated_at: datetime


class NotificationResponse(BaseModel):
    """Notification response."""

    id: UUID
    user_id: UUID
    type: NotificationType
    title: str
    message: str
    reference_id: Optional[UUID] = None
    reference_type: Optional[str] = None
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None
    actor_username: Optional[str] = None
    actor_display_name: Optional[str] = None


class NotificationListResponse(BaseModel):
    """List of notifications with pagination."""

    notifications: List[NotificationResponse]
    total_count: int
    unread_count: int
    page: int
    page_size: int


class UnreadCountResponse(BaseModel):
    """Unread notification count."""

    count: int


class MarkAllReadResponse(BaseModel):
    """Response after marking all as read."""

    marked_read: int
