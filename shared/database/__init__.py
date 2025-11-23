"""Shared database components for Colink services.

This package provides:
- Base SQLAlchemy model class
- Database session management
- Common models used across services
- Timestamp mixins
"""

from shared.database.base import Base, TimestampMixin, close_db, get_db, init_db
from shared.database.models import (
    AuditLog,
    Channel,
    ChannelMember,
    ChannelType,
    File,
    Message,
    MessageAttachment,
    MessageType,
    ModerationAction,
    ModerationActionModel,
    Notification,
    NotificationPreference,
    Reaction,
    Thread,
    User,
    UserRole,
    UserStatus,
)

__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    # Database functions
    "init_db",
    "get_db",
    "close_db",
    # Enums
    "UserStatus",
    "UserRole",
    "ChannelType",
    "MessageType",
    "ModerationAction",
    # User models
    "User",
    # Channel models
    "Channel",
    "ChannelMember",
    # Message models
    "Message",
    "MessageAttachment",
    # Thread models
    "Thread",
    # Reaction models
    "Reaction",
    # File models
    "File",
    # Admin models
    "AuditLog",
    "ModerationActionModel",
    # Notification models
    "Notification",
    "NotificationPreference",
]
