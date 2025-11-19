"""SQLAlchemy models for all Colink services.

This module contains all database models used across the Colink platform.
Models are organized by service domain:

1. Users Service: User, UserProfile
2. Channels Service: Channel, ChannelMember
3. Messaging Service: Message, MessageAttachment
4. Threads Service: Thread, ThreadMessage
5. Reactions Service: Reaction
6. Files Service: File
7. Admin Service: AuditLog, Moderation

All models inherit from Base and use the TimestampMixin for automatic
created_at/updated_at tracking.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database.base import Base, TimestampMixin


# ============================================================================
# Enums
# ============================================================================


class UserStatus(str, PyEnum):
    """User account status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class UserRole(str, PyEnum):
    """User role for RBAC."""

    ADMIN = "admin"
    MODERATOR = "moderator"
    MEMBER = "member"
    GUEST = "guest"


class ChannelType(str, PyEnum):
    """Channel visibility type."""

    PUBLIC = "public"
    PRIVATE = "private"
    DIRECT = "direct"


class MessageType(str, PyEnum):
    """Message content type."""

    TEXT = "text"
    SYSTEM = "system"
    FILE = "file"


class ModerationAction(str, PyEnum):
    """Admin moderation actions."""

    WARN = "warn"
    MUTE = "mute"
    SUSPEND = "suspend"
    DELETE_MESSAGE = "delete_message"
    DELETE_CHANNEL = "delete_channel"


# ============================================================================
# Users Service Models
# ============================================================================


class User(Base, TimestampMixin):
    """User account model.

    Stores core user information synced from Keycloak.
    """

    __tablename__ = "users"

    # Primary key - matches Keycloak user ID
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Core fields synced from Keycloak
    keycloak_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

    # Profile fields
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512))
    status_text: Mapped[Optional[str]] = mapped_column(String(255))

    # Status and role
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus), default=UserStatus.ACTIVE, nullable=False, index=True
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.MEMBER, nullable=False, index=True
    )

    # Metadata
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    # channels: Mapped[list["ChannelMember"]] = relationship(back_populates="user")
    # messages: Mapped[list["Message"]] = relationship(back_populates="author")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


# Note: Additional models will be added as we implement each service
# For now, we'll start with the User model and add more in subsequent steps

# Export Base for Alembic
__all__ = ["Base", "User", "UserStatus", "UserRole"]
