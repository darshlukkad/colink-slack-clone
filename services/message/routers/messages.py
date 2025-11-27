"""Message endpoints for Message Service."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.database import (
    Channel,
    Message,
    MessageType,
    Reaction,
    User,
    UserRole,
    get_db,
)

from ..dependencies import get_current_user, security, verify_channel_access
from ..services.kafka_producer import kafka_producer

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================


async def get_reactions_for_messages(
    message_ids: List[UUID],
    current_user_id: UUID,
    db: AsyncSession
) -> dict:
    """Get reactions for multiple messages grouped by message_id and emoji."""
    if not message_ids:
        return {}

    stmt = (
        select(Reaction, User)
        .join(User, Reaction.user_id == User.id)
        .where(Reaction.message_id.in_(message_ids))
    )
    result = await db.execute(stmt)
    reactions_with_users = result.all()

    # Group by message_id and emoji
    reactions_by_message = {}
    for reaction, user in reactions_with_users:
        message_id = str(reaction.message_id)
        if message_id not in reactions_by_message:
            reactions_by_message[message_id] = {}

        emoji = reaction.emoji
        if emoji not in reactions_by_message[message_id]:
            reactions_by_message[message_id][emoji] = {
                "emoji": emoji,
                "count": 0,
                "users": [],
                "user_reacted": False,
            }

        reactions_by_message[message_id][emoji]["count"] += 1
        reactions_by_message[message_id][emoji]["users"].append({
            "id": str(user.id),
            "username": user.username,
        })

        if reaction.user_id == current_user_id:
            reactions_by_message[message_id][emoji]["user_reacted"] = True

    # Convert to list format
    result_dict = {}
    for message_id, emojis in reactions_by_message.items():
        result_dict[message_id] = list(emojis.values())

    return result_dict


# ============================================================================
# Request/Response Models
# ============================================================================


class MessageCreate(BaseModel):
    """Request model for creating a message."""

    content: str = Field(..., min_length=1, max_length=4000, description="Message content")
    channel_id: UUID = Field(..., description="Channel ID where message will be sent")
    parent_id: Optional[UUID] = Field(None, description="Parent message ID for threads")
    message_type: MessageType = Field(MessageType.TEXT, description="Message type")


class MessageUpdate(BaseModel):
    """Request model for updating a message."""

    content: str = Field(..., min_length=1, max_length=4000, description="Updated message content")


class ReactionSummary(BaseModel):
    """Summary of reactions for a message."""
    emoji: str
    count: int
    users: List[dict]  # List of {id, username}
    user_reacted: bool = False


class MessageResponse(BaseModel):
    """Response model for a message."""

    id: UUID
    content: str
    channel_id: UUID
    author_id: UUID  # Changed from user_id
    thread_id: Optional[UUID] = None  # Changed from parent_id
    message_type: MessageType
    is_edited: bool = False  # Computed from edited_at
    is_deleted: bool = False  # Computed from deleted_at
    created_at: datetime
    updated_at: datetime
    edited_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    # Include author information
    author_username: Optional[str] = None
    author_display_name: Optional[str] = None

    # Thread information (if reply)
    parent_message_id: Optional[UUID] = None  # For API compatibility

    # Reactions
    reactions: Optional[List[ReactionSummary]] = None
    reply_count: Optional[int] = None

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Response model for a list of messages."""

    messages: List[MessageResponse]
    has_more: bool
    next_cursor: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    message_data: MessageCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new message in a channel.

    Requires:
    - User must be a member of the channel
    - If parent_id is provided, parent message must exist in the same channel
    """
    # Verify user has access to the channel
    await verify_channel_access(message_data.channel_id, current_user.id, db)

    # Handle threading (if parent_id is provided)
    thread_id = None
    if message_data.parent_id:
        # Find or create thread for the parent message
        from shared.database import Thread

        # Check if parent message exists
        parent_stmt = select(Message).where(
            Message.id == message_data.parent_id,
            Message.channel_id == message_data.channel_id
        )
        parent_result = await db.execute(parent_stmt)
        parent_message = parent_result.scalar_one_or_none()

        if not parent_message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent message not found in this channel",
            )

        # Find or create thread
        thread_stmt = select(Thread).where(Thread.root_message_id == message_data.parent_id)
        thread_result = await db.execute(thread_stmt)
        thread = thread_result.scalar_one_or_none()

        if not thread:
            # Create new thread
            thread = Thread(root_message_id=message_data.parent_id)
            db.add(thread)
            await db.flush()  # Get thread.id

        thread_id = thread.id

    # Create message
    message = Message(
        content=message_data.content,
        channel_id=message_data.channel_id,
        author_id=current_user.id,
        thread_id=thread_id,
        message_type=message_data.message_type,
    )

    db.add(message)
    await db.commit()
    await db.refresh(message)

    # Update thread metadata if this is a reply
    if thread_id and thread:
        thread.reply_count += 1
        thread.last_reply_at = message.created_at
        await db.commit()

    logger.info(
        f"Message created: {message.id} by user {current_user.id} in channel {message_data.channel_id}"
    )

    # Get parent message ID for API response (if this is a thread reply)
    parent_message_id = None
    if thread_id:
        # thread was already fetched if we got here
        stmt = select(Thread.root_message_id).where(Thread.id == thread_id)
        result = await db.execute(stmt)
        parent_message_id = result.scalar_one_or_none()

    # Publish event to Kafka
    await kafka_producer.publish_message_event(
        event_type="message.created",
        message_data={
            "id": str(message.id),
            "content": message.content,
            "channel_id": str(message.channel_id),
            "author_id": str(message.author_id),
            "thread_id": str(message.thread_id) if message.thread_id else None,
            "parent_message_id": str(parent_message_id) if parent_message_id else None,
            "message_type": message.message_type.value,
            "created_at": message.created_at.isoformat(),
            "author_username": current_user.username,
            "author_display_name": current_user.display_name,
        },
        key=str(message_data.channel_id),
    )

    # Build response
    response = MessageResponse(
        id=message.id,
        content=message.content,
        channel_id=message.channel_id,
        author_id=message.author_id,
        thread_id=message.thread_id,
        parent_message_id=parent_message_id,
        message_type=message.message_type,
        is_edited=message.edited_at is not None,
        is_deleted=message.deleted_at is not None,
        created_at=message.created_at,
        updated_at=message.updated_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
        author_username=current_user.username,
        author_display_name=current_user.display_name,
    )

    return response


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific message by ID.

    Requires:
    - User must be a member of the channel containing the message
    """
    # Get message with author information
    stmt = select(Message).options(selectinload(Message.author)).where(Message.id == message_id)
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    # Verify user has access to the channel
    await verify_channel_access(message.channel_id, current_user.id, db)

    # Get parent message ID if this is a thread reply
    parent_message_id = None
    if message.thread_id:
        from shared.database import Thread
        stmt = select(Thread.root_message_id).where(Thread.id == message.thread_id)
        result = await db.execute(stmt)
        parent_message_id = result.scalar_one_or_none()

    # Build response
    response = MessageResponse(
        id=message.id,
        content=message.content if not message.deleted_at else "[Message deleted]",
        channel_id=message.channel_id,
        author_id=message.author_id,
        thread_id=message.thread_id,
        parent_message_id=parent_message_id,
        message_type=message.message_type,
        is_edited=message.edited_at is not None,
        is_deleted=message.deleted_at is not None,
        created_at=message.created_at,
        updated_at=message.updated_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
        author_username=message.author.username if message.author else None,
        author_display_name=message.author.display_name if message.author else None,
    )

    return response


@router.get("/channels/{channel_id}/messages", response_model=MessageListResponse)
async def get_channel_messages(
    channel_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100, description="Number of messages to return"),
    before: Optional[str] = Query(None, description="Get messages before this cursor (message ID)"),
    after: Optional[str] = Query(None, description="Get messages after this cursor (message ID)"),
):
    """Get messages in a channel with pagination.

    Supports cursor-based pagination using message IDs.

    Requires:
    - User must be a member of the channel
    """
    # Verify user has access to the channel
    await verify_channel_access(channel_id, current_user.id, db)

    # Build query
    stmt = (
        select(Message)
        .options(selectinload(Message.author))
        .where(
            Message.channel_id == channel_id,
            Message.thread_id.is_(None),  # Only top-level messages (not thread replies)
            Message.deleted_at.is_(None),  # Don't show deleted messages
        )
        .order_by(desc(Message.created_at))
    )

    # Apply cursor pagination
    if before:
        # Get messages before this cursor
        cursor_stmt = select(Message).where(Message.id == UUID(before))
        cursor_result = await db.execute(cursor_stmt)
        cursor_message = cursor_result.scalar_one_or_none()

        if cursor_message:
            stmt = stmt.where(Message.created_at < cursor_message.created_at)

    elif after:
        # Get messages after this cursor
        cursor_stmt = select(Message).where(Message.id == UUID(after))
        cursor_result = await db.execute(cursor_stmt)
        cursor_message = cursor_result.scalar_one_or_none()

        if cursor_message:
            stmt = stmt.where(Message.created_at > cursor_message.created_at)

    # Fetch messages (limit + 1 to check if there are more)
    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    messages = result.scalars().all()

    # Check if there are more messages
    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    # Fetch reactions for all messages
    message_ids = [message.id for message in messages]
    reactions_by_message = await get_reactions_for_messages(message_ids, current_user.id, db)

    # Build response
    message_responses = []
    for message in messages:
        message_id_str = str(message.id)
        reactions = reactions_by_message.get(message_id_str, [])

        message_responses.append(
            MessageResponse(
                id=message.id,
                content=message.content,
                channel_id=message.channel_id,
                author_id=message.author_id,
                thread_id=message.thread_id,
                message_type=message.message_type,
                is_edited=message.edited_at is not None,
                is_deleted=message.deleted_at is not None,
                created_at=message.created_at,
                updated_at=message.updated_at,
                edited_at=message.edited_at,
                deleted_at=message.deleted_at,
                author_username=message.author.username if message.author else None,
                author_display_name=message.author.display_name if message.author else None,
                reactions=reactions if reactions else None,
            )
        )

    # Calculate next cursor
    next_cursor = str(messages[-1].id) if has_more and messages else None

    return MessageListResponse(
        messages=message_responses,
        has_more=has_more,
        next_cursor=next_cursor,
    )


@router.put("/messages/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: UUID,
    message_update: MessageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a message.

    Requires:
    - User must be the author of the message
    """
    # Get message
    stmt = select(Message).options(selectinload(Message.author)).where(Message.id == message_id)
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    # Verify user is the author
    if message.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own messages",
        )

    # Verify message is not deleted
    if message.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit a deleted message",
        )

    # Update message
    message.content = message_update.content
    message.edited_at = datetime.now(timezone.utc)
    message.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(message)

    logger.info(f"Message updated: {message.id} by user {current_user.id}")

    # Publish event to Kafka
    await kafka_producer.publish_message_event(
        event_type="message.updated",
        message_data={
            "id": str(message.id),
            "content": message.content,
            "channel_id": str(message.channel_id),
            "author_id": str(message.author_id),
            "is_edited": message.edited_at is not None,
            "edited_at": message.edited_at.isoformat() if message.edited_at else None,
            "updated_at": message.updated_at.isoformat(),
        },
        key=str(message.channel_id),
    )

    # Build response
    response = MessageResponse(
        id=message.id,
        content=message.content,
        channel_id=message.channel_id,
        author_id=message.author_id,
        thread_id=message.thread_id,
        message_type=message.message_type,
        is_edited=message.edited_at is not None,
        is_deleted=message.deleted_at is not None,
        created_at=message.created_at,
        updated_at=message.updated_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
        author_username=message.author.username if message.author else None,
        author_display_name=message.author.display_name if message.author else None,
    )

    return response


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a message (soft delete).

    Requires:
    - User must be the author of the message, OR
    - User must be an admin or moderator
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

    # Verify user is the author or has admin/moderator role
    is_author = message.author_id == current_user.id
    is_moderator = current_user.role in [UserRole.ADMIN, UserRole.MODERATOR]

    if not (is_author or is_moderator):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this message",
        )

    # Soft delete the message
    message.deleted_at = datetime.now(timezone.utc)
    message.content = "[Message deleted]"
    message.updated_at = datetime.now(timezone.utc)

    await db.commit()

    logger.info(f"Message deleted: {message.id} by user {current_user.id}")

    # Publish event to Kafka
    await kafka_producer.publish_message_event(
        event_type="message.deleted",
        message_data={
            "id": str(message.id),
            "channel_id": str(message.channel_id),
            "deleted_by": str(current_user.id),
        },
        key=str(message.channel_id),
    )

    return None
