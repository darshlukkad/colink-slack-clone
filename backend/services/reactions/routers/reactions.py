"""Reaction endpoints for Reactions Service."""

import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from shared.database import Message, Reaction, User, get_db

from ..dependencies import (
    get_current_user,
    security,
    verify_message_access,
)
from ..schemas.reactions import (
    ReactionCreate,
    ReactionListResponse,
    ReactionResponse,
    ReactionSummaryItem,
    ReactionSummaryResponse,
)
from ..services.kafka_producer import kafka_producer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/messages/{message_id}/reactions",
    response_model=ReactionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(security)],
)
async def add_reaction(
    message_id: UUID,
    reaction_data: ReactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a reaction to a message.

    Requires:
    - User must be a member of the channel containing the message
    - Message must exist and not be deleted
    - One user can only react once with the same emoji per message
    """
    # Verify message access
    message = await verify_message_access(message_id, current_user.id, db)

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
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reacted with this emoji",
        )

    # Create reaction
    try:
        reaction = Reaction(
            message_id=message_id,
            user_id=current_user.id,
            emoji=reaction_data.emoji,
        )
        db.add(reaction)
        await db.commit()
        await db.refresh(reaction)

        # Publish reaction.added event
        await kafka_producer.publish_event(
            topic="reactions",
            key=str(message_id),
            event_type="reaction.added",
            data={
                "reaction_id": str(reaction.id),
                "message_id": str(message_id),
                "channel_id": str(message.channel_id),
                "user_id": str(current_user.id),
                "username": current_user.username,
                "emoji": reaction_data.emoji,
                "created_at": reaction.created_at.isoformat(),
            },
        )

        logger.info(
            f"User {current_user.id} added reaction {reaction_data.emoji} to message {message_id}"
        )

        return ReactionResponse(
            id=reaction.id,
            message_id=reaction.message_id,
            user_id=reaction.user_id,
            username=current_user.username,
            display_name=current_user.display_name,
            emoji=reaction.emoji,
            created_at=reaction.created_at,
        )

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reaction already exists",
        )


@router.delete(
    "/messages/{message_id}/reactions/{emoji}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(security)],
)
async def remove_reaction(
    message_id: UUID,
    emoji: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove your reaction from a message.

    Requires:
    - User must be a member of the channel containing the message
    - User can only remove their own reactions
    """
    # Verify message access
    message = await verify_message_access(message_id, current_user.id, db)

    # Find the reaction
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

    # Delete the reaction
    await db.delete(reaction)
    await db.commit()

    # Publish reaction.removed event
    await kafka_producer.publish_event(
        topic="reactions",
        key=str(message_id),
        event_type="reaction.removed",
        data={
            "reaction_id": str(reaction.id),
            "message_id": str(message_id),
            "channel_id": str(message.channel_id),
            "user_id": str(current_user.id),
            "username": current_user.username,
            "emoji": emoji,
            "removed_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    logger.info(
        f"User {current_user.id} removed reaction {emoji} from message {message_id}"
    )


@router.get(
    "/messages/{message_id}/reactions",
    response_model=ReactionListResponse,
    dependencies=[Depends(security)],
)
async def list_reactions(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all reactions on a message.

    Requires:
    - User must be a member of the channel containing the message
    """
    # Verify message access
    await verify_message_access(message_id, current_user.id, db)

    # Get all reactions with user info
    stmt = (
        select(Reaction, User)
        .join(User, Reaction.user_id == User.id)
        .where(Reaction.message_id == message_id)
        .order_by(Reaction.created_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    reactions = []
    for reaction, user in rows:
        reactions.append(
            ReactionResponse(
                id=reaction.id,
                message_id=reaction.message_id,
                user_id=reaction.user_id,
                username=user.username,
                display_name=user.display_name,
                emoji=reaction.emoji,
                created_at=reaction.created_at,
            )
        )

    logger.info(f"Retrieved {len(reactions)} reactions for message {message_id}")

    return ReactionListResponse(
        message_id=message_id,
        total_count=len(reactions),
        reactions=reactions,
    )


@router.get(
    "/messages/{message_id}/reactions/summary",
    response_model=ReactionSummaryResponse,
    dependencies=[Depends(security)],
)
async def get_reaction_summary(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get reaction summary (grouped by emoji) for a message.

    Requires:
    - User must be a member of the channel containing the message

    Returns:
    - List of emojis with count and list of users who reacted
    - Whether the current user reacted with each emoji
    """
    # Verify message access
    await verify_message_access(message_id, current_user.id, db)

    # Get all reactions grouped by emoji
    stmt = (
        select(Reaction, User)
        .join(User, Reaction.user_id == User.id)
        .where(Reaction.message_id == message_id)
        .order_by(Reaction.emoji, Reaction.created_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Group reactions by emoji
    emoji_map = {}
    for reaction, user in rows:
        if reaction.emoji not in emoji_map:
            emoji_map[reaction.emoji] = {
                "count": 0,
                "users": [],
                "user_reacted": False,
            }

        emoji_map[reaction.emoji]["count"] += 1
        emoji_map[reaction.emoji]["users"].append(user.username)

        if reaction.user_id == current_user.id:
            emoji_map[reaction.emoji]["user_reacted"] = True

    # Convert to response format
    reactions = []
    for emoji, data in emoji_map.items():
        reactions.append(
            ReactionSummaryItem(
                emoji=emoji,
                count=data["count"],
                users=data["users"],
                user_reacted=data["user_reacted"],
            )
        )

    # Sort by count (descending), then by emoji
    reactions.sort(key=lambda x: (-x.count, x.emoji))

    total_reactions = sum(r.count for r in reactions)

    logger.info(
        f"Retrieved reaction summary for message {message_id}: {len(reactions)} unique emojis, {total_reactions} total"
    )

    return ReactionSummaryResponse(
        message_id=message_id,
        total_reactions=total_reactions,
        reactions=reactions,
    )
