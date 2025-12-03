"""Pydantic schemas for Thread service."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Reaction Schemas
# ============================================================================


class ReactionSummary(BaseModel):
    """Summary of reactions for a message."""
    emoji: str
    count: int
    users: List[Dict[str, Any]]  # List of {id, username}
    user_reacted: bool = False


# ============================================================================
# Thread Schemas
# ============================================================================


class ThreadCreate(BaseModel):
    """Request model for creating a thread (usually auto-created with first reply)."""

    root_message_id: UUID = Field(..., description="Root message ID that starts this thread")


class ThreadUpdate(BaseModel):
    """Request model for updating thread metadata."""

    # Currently threads are auto-managed, but could add manual fields later
    # e.g., is_resolved, pinned, etc.
    pass


class ThreadResponse(BaseModel):
    """Response model for a thread."""

    id: UUID
    root_message_id: UUID
    channel_id: UUID  # Derived from root message
    reply_count: int
    participant_count: int
    last_reply_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Additional computed fields
    root_message_content: Optional[str] = None
    root_message_author: Optional[str] = None

    class Config:
        from_attributes = True


class ThreadReplyResponse(BaseModel):
    """Response model for a message that is a thread reply."""

    id: UUID
    content: str
    author_id: UUID
    author_username: Optional[str] = None
    author_display_name: Optional[str] = None
    thread_id: UUID
    message_type: str
    is_edited: bool = False
    created_at: datetime
    updated_at: datetime
    edited_at: Optional[datetime] = None
    reactions: List[ReactionSummary] = []

    class Config:
        from_attributes = True


class ThreadListResponse(BaseModel):
    """Response model for a list of threads."""

    threads: List[ThreadResponse]
    total_count: int
    has_more: bool = False
    next_cursor: Optional[str] = None


class ThreadParticipantResponse(BaseModel):
    """Response model for thread participant."""

    user_id: UUID
    username: str
    display_name: Optional[str] = None
    reply_count: int  # How many replies this user contributed
    first_reply_at: datetime
    last_reply_at: datetime


class ThreadParticipantsResponse(BaseModel):
    """Response model for thread participants list."""

    participants: List[ThreadParticipantResponse]
    total_count: int


class ThreadRepliesResponse(BaseModel):
    """Response model for thread replies list."""

    replies: List[ThreadReplyResponse]
    total_count: int
    has_more: bool = False
