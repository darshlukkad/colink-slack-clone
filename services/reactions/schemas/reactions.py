"""Pydantic schemas for reaction operations."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ReactionCreate(BaseModel):
    """Schema for creating a reaction."""

    emoji: str = Field(..., description="Emoji unicode or :name: format")

    @field_validator("emoji")
    @classmethod
    def validate_emoji(cls, v: str) -> str:
        """Validate emoji format."""
        if not v or len(v) > 100:
            raise ValueError("Emoji must be between 1 and 100 characters")
        return v.strip()


class ReactionResponse(BaseModel):
    """Schema for reaction response."""

    id: UUID
    message_id: UUID
    user_id: UUID
    username: str
    display_name: Optional[str]
    emoji: str
    created_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True


class ReactionSummaryItem(BaseModel):
    """Schema for reaction summary per emoji."""

    emoji: str
    count: int
    users: List[str] = Field(
        description="List of usernames who reacted with this emoji"
    )
    user_reacted: bool = Field(
        description="Whether current user reacted with this emoji"
    )


class ReactionSummaryResponse(BaseModel):
    """Schema for reaction summary response."""

    message_id: UUID
    total_reactions: int
    reactions: List[ReactionSummaryItem]


class ReactionListResponse(BaseModel):
    """Schema for listing all reactions on a message."""

    message_id: UUID
    total_count: int
    reactions: List[ReactionResponse]
