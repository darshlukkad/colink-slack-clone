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

    public = "PUBLIC"
    private = "PRIVATE"
    direct = "DIRECT"


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


# ============================================================================
# Channels Service Models
# ============================================================================


class Channel(Base, TimestampMixin):
    """Channel model for public/private channels and direct messages.

    Supports three types:
    - PUBLIC: Anyone can join
    - PRIVATE: Invite-only
    - DIRECT: One-on-one or small group DMs
    """

    __tablename__ = "channels"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Channel metadata
    name: Mapped[Optional[str]] = mapped_column(
        String(100), index=True
    )  # NULL for direct messages
    description: Mapped[Optional[str]] = mapped_column(Text)
    topic: Mapped[Optional[str]] = mapped_column(String(255))

    # Channel type and visibility
    channel_type: Mapped[ChannelType] = mapped_column(
        String(20), default=ChannelType.public.value, nullable=False, index=True
    )

    # Creator and ownership
    created_by_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    # Metadata
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_id])
    members: Mapped[list["ChannelMember"]] = relationship(
        "ChannelMember", back_populates="channel", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="channel", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Channel(id={self.id}, name={self.name}, type={self.channel_type})>"


class ChannelMember(Base, TimestampMixin):
    """Channel membership with role-based permissions."""

    __tablename__ = "channel_members"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    channel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Member role (admin can manage channel, member is regular user)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Notification preferences
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    muted_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Last read tracking
    last_read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Soft delete (when user leaves channel)
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="members")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_channel_members_channel_user"),
        Index("ix_channel_members_channel_id", "channel_id"),
        Index("ix_channel_members_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<ChannelMember(channel_id={self.channel_id}, user_id={self.user_id})>"


# ============================================================================
# Messaging Service Models
# ============================================================================


class Message(Base, TimestampMixin):
    """Message model for channel and direct messages."""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    channel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Message content
    content: Mapped[Optional[str]] = mapped_column(Text)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType), default=MessageType.TEXT, nullable=False, index=True
    )

    # Thread reference (if this message is part of a thread)
    thread_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("threads.id", ondelete="SET NULL")
    )

    # Editing tracking
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    # Metadata (mentions, links, etc.)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="messages")
    author: Mapped[Optional["User"]] = relationship("User")
    thread: Mapped[Optional["Thread"]] = relationship("Thread", foreign_keys=[thread_id])
    attachments: Mapped[list["MessageAttachment"]] = relationship(
        "MessageAttachment", back_populates="message", cascade="all, delete-orphan"
    )
    reactions: Mapped[list["Reaction"]] = relationship(
        "Reaction", back_populates="message", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_messages_channel_id_created_at", "channel_id", "created_at"),
        Index("ix_messages_author_id", "author_id"),
        Index("ix_messages_thread_id", "thread_id"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, channel_id={self.channel_id}, author_id={self.author_id})>"


class MessageAttachment(Base, TimestampMixin):
    """File attachments on messages."""

    __tablename__ = "message_attachments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    message_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="attachments")
    file: Mapped["File"] = relationship("File")

    __table_args__ = (
        Index("ix_message_attachments_message_id", "message_id"),
        Index("ix_message_attachments_file_id", "file_id"),
    )

    def __repr__(self) -> str:
        return f"<MessageAttachment(message_id={self.message_id}, file_id={self.file_id})>"


# ============================================================================
# Threads Service Models
# ============================================================================


class Thread(Base, TimestampMixin):
    """Discussion thread on a message."""

    __tablename__ = "threads"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # The root message that started this thread
    root_message_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Thread metadata
    reply_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    participant_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Last activity tracking
    last_reply_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True
    )

    # Relationships
    root_message: Mapped["Message"] = relationship(
        "Message", foreign_keys=[root_message_id], overlaps="thread"
    )

    __table_args__ = (Index("ix_threads_last_reply_at", "last_reply_at"),)

    def __repr__(self) -> str:
        return f"<Thread(id={self.id}, root_message_id={self.root_message_id}, replies={self.reply_count})>"


# ============================================================================
# Reactions Service Models
# ============================================================================


class Reaction(Base, TimestampMixin):
    """Emoji reactions on messages."""

    __tablename__ = "reactions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    message_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Emoji (e.g., "👍", "❤️", ":rocket:")
    emoji: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="reactions")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_reactions_message_user_emoji"),
        Index("ix_reactions_message_id", "message_id"),
        Index("ix_reactions_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<Reaction(message_id={self.message_id}, user_id={self.user_id}, emoji={self.emoji})>"


# ============================================================================
# Files Service Models
# ============================================================================


class File(Base, TimestampMixin):
    """File metadata and storage references."""

    __tablename__ = "files"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Uploader
    uploaded_by_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # File metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Storage location (MinIO/S3)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    bucket: Mapped[str] = mapped_column(String(100), nullable=False)

    # URLs
    url: Mapped[Optional[str]] = mapped_column(String(1024))
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024))

    # Virus scan status
    scan_status: Mapped[Optional[str]] = mapped_column(
        String(50), default="pending", index=True
    )  # pending, clean, infected
    scanned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    # Metadata
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    uploaded_by: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        Index("ix_files_uploaded_by_id", "uploaded_by_id"),
        Index("ix_files_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<File(id={self.id}, filename={self.filename}, size={self.size_bytes})>"


# ============================================================================
# Admin Service Models
# ============================================================================


class AuditLog(Base, TimestampMixin):
    """Audit log for tracking admin and system actions."""

    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Actor (who performed the action)
    actor_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # Action details
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # user, channel, message, etc.
    resource_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True))

    # Changes (JSON diff of before/after)
    changes: Mapped[Optional[dict]] = mapped_column(JSONB)

    # IP address and user agent
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))

    # Relationships
    actor: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        Index("ix_audit_logs_actor_id", "actor_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_resource_type", "resource_type"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, actor_id={self.actor_id})>"


class ModerationActionModel(Base, TimestampMixin):
    """Moderation actions taken against users."""

    __tablename__ = "moderation_actions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Target user
    target_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Moderator
    moderator_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Action details
    action_type: Mapped[ModerationAction] = mapped_column(
        Enum(ModerationAction), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Duration (for temporary actions like mute/suspend)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    # Related resources (e.g., message_id if deleting a message)
    resource_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_by_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # Relationships
    target_user: Mapped["User"] = relationship("User", foreign_keys=[target_user_id])
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderator_id])
    revoked_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[revoked_by_id])

    __table_args__ = (
        Index("ix_moderation_actions_target_user_id", "target_user_id"),
        Index("ix_moderation_actions_moderator_id", "moderator_id"),
        Index("ix_moderation_actions_action_type", "action_type"),
        Index("ix_moderation_actions_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<ModerationAction(id={self.id}, action={self.action_type}, target={self.target_user_id})>"


# ============================================================================
# Notifications Service Models
# ============================================================================


class Notification(Base, TimestampMixin):
    """User notifications model."""

    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Target user
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Notification details
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # mention, reaction, reply, etc.
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Reference to related entity
    reference_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True))  # message_id, channel_id, etc.
    reference_type: Mapped[Optional[str]] = mapped_column(String(50))  # 'message', 'channel', etc.

    # Who triggered this notification
    actor_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # Read status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        Index("ix_notifications_user_id_is_read", "user_id", "is_read"),
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
        Index("ix_notifications_type", "type"),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.type})>"


class NotificationPreference(Base, TimestampMixin):
    """User notification preferences."""

    __tablename__ = "notification_preferences"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # User
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    # Preference flags
    mentions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reactions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    replies: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    direct_messages: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    channel_updates: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<NotificationPreference(user_id={self.user_id})>"


# Export all models for Alembic
__all__ = [
    "Base",
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
