"""Reaction endpoints for Message Service."""

import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Message, Reaction, User, get_db

from ..dependencies import get_current_user, verify_channel_access
from ..services.kafka_producer import kafka_producer

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class ReactionCreate(BaseModel):
    """Request model for adding a reaction."""

    emoji: str = Field(..., min_length=1, max_length=50, description="Emoji or reaction text")


class ReactionResponse(BaseModel):
    """Response model for a reaction."""

    id: UUID
    message_id: UUID
    user_id: UUID
    emoji: str
    created_at: datetime

    # Include user information
    username: str

    class Config:
        from_attributes = True


class ReactionSummary(BaseModel):
    """Summary of reactions for a message."""

    emoji: str
    count: int
    users: List[str]  # List of usernames who reacted


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/messages/{message_id}/reactions",
    response_model=ReactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_reaction(
    message_id: UUID,
    reaction_data: ReactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a reaction to a message.

    Requires:
    - Message must exist
    - User must be a member of the channel
    - User can only add one reaction of each emoji type per message
    """
    # Get message
    stmt = select(Message).where(Message.id == message_id)
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    # Verify user has access to the channel
    await verify_channel_access(message.channel_id, current_user.id, db)

    # Check if user already reacted with this emoji
    stmt = select(Reaction).where(
        and_(
            Reaction.message_id == message_id,
            Reaction.user_id == current_user.id,
            Reaction.emoji == reaction_data.emoji,
        )
    )
    result = await db.execute(stmt)
    existing_reaction = result.scalar_one_or_none()

    if existing_reaction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reacted with this emoji",
        )

    # Create reaction
    reaction = Reaction(
        message_id=message_id,
        user_id=current_user.id,
        emoji=reaction_data.emoji,
    )

    db.add(reaction)
    await db.commit()
    await db.refresh(reaction)

    logger.info(
        f"Reaction added: {reaction.emoji} by user {current_user.id} on message {message_id}"
    )

    # Publish event to Kafka
    await kafka_producer.publish_reaction_event(
        event_type="reaction.added",
        reaction_data={
            "id": str(reaction.id),
            "message_id": str(message_id),
            "channel_id": str(message.channel_id),
            "user_id": str(current_user.id),
            "username": current_user.username,
            "emoji": reaction.emoji,
            "created_at": reaction.created_at.isoformat(),
        },
        key=str(message_id),
    )

    return ReactionResponse(
        id=reaction.id,
        message_id=reaction.message_id,
        user_id=reaction.user_id,
        emoji=reaction.emoji,
        created_at=reaction.created_at,
        username=current_user.username,
    )


@router.delete("/messages/{message_id}/reactions/{emoji}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_reaction(
    message_id: UUID,
    emoji: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a reaction from a message.

    Requires:
    - User must have previously added this reaction
    """
    # Get message
    stmt = select(Message).where(Message.id == message_id)
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    # Get reaction
    stmt = select(Reaction).where(
        and_(
            Reaction.message_id == message_id,
            Reaction.user_id == current_user.id,
            Reaction.emoji == emoji,
        )
    )
    result = await db.execute(stmt)
    reaction = result.scalar_one_or_none()

    if not reaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reaction not found",
        )

    # Delete reaction
    await db.delete(reaction)
    await db.commit()

    logger.info(f"Reaction removed: {emoji} by user {current_user.id} from message {message_id}")

    # Publish event to Kafka
    await kafka_producer.publish_reaction_event(
        event_type="reaction.removed",
        reaction_data={
            "message_id": str(message_id),
            "channel_id": str(message.channel_id),
            "user_id": str(current_user.id),
            "username": current_user.username,
            "emoji": emoji,
        },
        key=str(message_id),
    )

    return None


@router.get("/messages/{message_id}/reactions", response_model=List[ReactionSummary])
async def get_message_reactions(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all reactions for a message, grouped by emoji.

    Requires:
    - User must be a member of the channel
    """
    # Get message
    stmt = select(Message).where(Message.id == message_id)
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    # Verify user has access to the channel
    await verify_channel_access(message.channel_id, current_user.id, db)

    # Get all reactions for this message
    stmt = (
        select(Reaction, User)
        .join(User, Reaction.user_id == User.id)
        .where(Reaction.message_id == message_id)
    )
    result = await db.execute(stmt)
    reactions = result.all()

    # Group reactions by emoji
    reaction_groups = {}
    for reaction, user in reactions:
        if reaction.emoji not in reaction_groups:
            reaction_groups[reaction.emoji] = {
                "emoji": reaction.emoji,
                "count": 0,
                "users": [],
            }
        reaction_groups[reaction.emoji]["count"] += 1
        reaction_groups[reaction.emoji]["users"].append(user.username)

    # Convert to list
    reaction_summaries = [
        ReactionSummary(**data) for data in reaction_groups.values()
    ]

    return reaction_summaries
