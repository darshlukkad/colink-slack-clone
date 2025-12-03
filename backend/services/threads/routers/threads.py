"""Thread endpoints for Threads Service."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.database import Channel, Message, MessageType, Reaction, Thread, User, get_db

from ..dependencies import (
    get_current_user,
    get_pagination_params,
    security,
    verify_channel_access,
    verify_thread_access,
)
from ..schemas.threads import (
    ReactionSummary,
    ThreadListResponse,
    ThreadParticipantResponse,
    ThreadParticipantsResponse,
    ThreadRepliesResponse,
    ThreadReplyResponse,
    ThreadResponse,
)
from ..services.kafka_producer import kafka_producer

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================


async def get_reactions_for_messages(
    message_ids: List[UUID],
    current_user_id: UUID,
    db: AsyncSession,
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
        reactions_by_message[message_id][emoji]["users"].append(
            {"id": str(user.id), "username": user.username}
        )
        if reaction.user_id == current_user_id:
            reactions_by_message[message_id][emoji]["user_reacted"] = True

    # Convert to list format
    result_dict = {}
    for message_id, emojis in reactions_by_message.items():
        result_dict[message_id] = [
            ReactionSummary(**reaction_data) for reaction_data in emojis.values()
        ]

    return result_dict


async def get_thread_with_details(
    thread_id: UUID,
    db: AsyncSession,
) -> Optional[ThreadResponse]:
    """Get thread with additional details like root message info."""
    stmt = (
        select(Thread, Message, User)
        .join(Message, Thread.root_message_id == Message.id)
        .join(User, Message.author_id == User.id)
        .where(Thread.id == thread_id)
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        return None

    thread, root_message, author = row

    # Get channel_id from root message
    return ThreadResponse(
        id=thread.id,
        root_message_id=thread.root_message_id,
        channel_id=root_message.channel_id,
        reply_count=thread.reply_count,
        participant_count=thread.participant_count,
        last_reply_at=thread.last_reply_at,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        root_message_content=root_message.content,
        root_message_author=author.username,
    )


async def update_thread_stats(
    thread_id: UUID,
    db: AsyncSession,
) -> None:
    """Update thread reply count and participant count."""
    # Get all messages in this thread
    stmt = select(Message).where(
        Message.thread_id == thread_id,
        Message.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    # Count replies and unique participants
    reply_count = len(messages)
    participant_ids = {msg.author_id for msg in messages if msg.author_id}
    participant_count = len(participant_ids)

    # Get last reply time
    last_reply_at = max((msg.created_at for msg in messages), default=None)

    # Update thread
    stmt = select(Thread).where(Thread.id == thread_id)
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    if thread:
        thread.reply_count = reply_count
        thread.participant_count = participant_count
        thread.last_reply_at = last_reply_at
        await db.commit()


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/threads/{thread_id}",
    response_model=ThreadResponse,
    dependencies=[Depends(security)],
)
async def get_thread(
    thread_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get thread details.

    Requires:
    - User must be a member of the channel containing the thread
    """
    # Verify access
    await verify_thread_access(thread_id, current_user.id, db)

    # Get thread with details
    thread_response = await get_thread_with_details(thread_id, db)

    if not thread_response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    return thread_response


@router.get(
    "/threads/{thread_id}/replies",
    response_model=ThreadRepliesResponse,
    dependencies=[Depends(security)],
)
async def get_thread_replies(
    thread_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all replies in a thread (paginated).

    Requires:
    - User must be a member of the channel containing the thread
    """
    # Verify access
    await verify_thread_access(thread_id, current_user.id, db)

    # Get total count
    count_stmt = (
        select(func.count())
        .select_from(Message)
        .where(
            Message.thread_id == thread_id,
            Message.deleted_at.is_(None),
        )
    )
    count_result = await db.execute(count_stmt)
    total_count = count_result.scalar() or 0

    # Get replies
    stmt = (
        select(Message, User)
        .join(User, Message.author_id == User.id)
        .where(
            Message.thread_id == thread_id,
            Message.deleted_at.is_(None),
        )
        .order_by(Message.created_at)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Get reactions for all messages
    message_ids = [message.id for message, _ in rows]
    reactions_map = await get_reactions_for_messages(
        message_ids, current_user.id, db
    )

    replies = []
    for message, author in rows:
        message_reactions = reactions_map.get(str(message.id), [])
        replies.append(
            ThreadReplyResponse(
                id=message.id,
                content=message.content,
                author_id=message.author_id,
                author_username=author.username,
                author_display_name=author.display_name,
                thread_id=message.thread_id,
                message_type=message.message_type,
                is_edited=message.edited_at is not None,
                created_at=message.created_at,
                updated_at=message.updated_at,
                edited_at=message.edited_at,
                reactions=message_reactions,
            )
        )

    logger.info(f"Retrieved {len(replies)} replies for thread {thread_id}")

    return ThreadRepliesResponse(
        replies=replies,
        total_count=total_count,
        has_more=(offset + len(replies)) < total_count,
    )


@router.get(
    "/messages/{message_id}/replies",
    response_model=ThreadRepliesResponse,
    dependencies=[Depends(security)],
)
async def get_message_replies(
    message_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all replies to a specific message (by parent message ID).

    This is useful when the thread may not exist yet, or when you only have the parent message ID.

    Requires:
    - User must be a member of the channel containing the message
    """
    # Get the parent message to verify it exists and get channel_id
    stmt = select(Message).where(Message.id == message_id)
    result = await db.execute(stmt)
    parent_message = result.scalar_one_or_none()

    if not parent_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent message not found",
        )

    # Verify channel access
    await verify_channel_access(parent_message.channel_id, current_user.id, db)

    # Find the thread for this parent message
    stmt = select(Thread).where(Thread.root_message_id == message_id)
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    # If no thread exists yet, return empty results
    if not thread:
        return ThreadRepliesResponse(
            replies=[],
            total_count=0,
            has_more=False,
        )

    # Get total count
    count_stmt = (
        select(func.count())
        .select_from(Message)
        .where(
            Message.thread_id == thread.id,
            Message.deleted_at.is_(None),
        )
    )
    count_result = await db.execute(count_stmt)
    total_count = count_result.scalar() or 0

    # Get replies
    stmt = (
        select(Message, User)
        .join(User, Message.author_id == User.id)
        .where(
            Message.thread_id == thread.id,
            Message.deleted_at.is_(None),
        )
        .order_by(Message.created_at)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Get reactions for all messages
    message_ids = [message.id for message, _ in rows]
    reactions_map = await get_reactions_for_messages(
        message_ids, current_user.id, db
    )

    replies = []
    for message, author in rows:
        message_reactions = reactions_map.get(str(message.id), [])
        replies.append(
            ThreadReplyResponse(
                id=message.id,
                content=message.content,
                author_id=message.author_id,
                author_username=author.username,
                author_display_name=author.display_name,
                thread_id=message.thread_id,
                message_type=message.message_type,
                is_edited=message.edited_at is not None,
                created_at=message.created_at,
                updated_at=message.updated_at,
                edited_at=message.edited_at,
                reactions=message_reactions,
            )
        )

    logger.info(f"Retrieved {len(replies)} replies for message {message_id}")

    return ThreadRepliesResponse(
        replies=replies,
        total_count=total_count,
        has_more=(offset + len(replies)) < total_count,
    )


@router.get(
    "/channels/{channel_id}/threads",
    response_model=ThreadListResponse,
    dependencies=[Depends(security)],
)
async def get_channel_threads(
    channel_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    active_only: bool = Query(False, description="Only show recently active threads"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all threads in a channel.

    Requires:
    - User must be a member of the channel
    """
    # Verify channel access
    await verify_channel_access(channel_id, current_user.id, db)

    # Build query to get threads
    # Join threads with messages to get channel_id
    stmt = (
        select(Thread, Message)
        .join(Message, Thread.root_message_id == Message.id)
        .where(
            Message.channel_id == channel_id,
            Message.deleted_at.is_(None),
        )
    )

    if active_only:
        stmt = stmt.where(Thread.last_reply_at.isnot(None))

    stmt = stmt.order_by(desc(Thread.last_reply_at)).limit(limit + 1).offset(offset)

    result = await db.execute(stmt)
    rows = result.all()

    has_more = len(rows) > limit
    threads_data = rows[:limit]

    threads = []
    for thread, root_message in threads_data:
        # Get root message author
        stmt = select(User).where(User.id == root_message.author_id)
        result = await db.execute(stmt)
        author = result.scalar_one_or_none()

        threads.append(
            ThreadResponse(
                id=thread.id,
                root_message_id=thread.root_message_id,
                channel_id=root_message.channel_id,
                reply_count=thread.reply_count,
                participant_count=thread.participant_count,
                last_reply_at=thread.last_reply_at,
                created_at=thread.created_at,
                updated_at=thread.updated_at,
                root_message_content=root_message.content,
                root_message_author=author.username if author else None,
            )
        )

    # Get total count
    count_stmt = (
        select(func.count(Thread.id))
        .join(Message, Thread.root_message_id == Message.id)
        .where(
            Message.channel_id == channel_id,
            Message.deleted_at.is_(None),
        )
    )
    if active_only:
        count_stmt = count_stmt.where(Thread.last_reply_at.isnot(None))

    result = await db.execute(count_stmt)
    total_count = result.scalar() or 0

    logger.info(f"Retrieved {len(threads)} threads for channel {channel_id}")

    return ThreadListResponse(
        threads=threads,
        total_count=total_count,
        has_more=has_more,
        next_cursor=str(offset + limit) if has_more else None,
    )


@router.get(
    "/threads/{thread_id}/participants",
    response_model=ThreadParticipantsResponse,
    dependencies=[Depends(security)],
)
async def get_thread_participants(
    thread_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all participants in a thread.

    Requires:
    - User must be a member of the channel containing the thread
    """
    # Verify access
    await verify_thread_access(thread_id, current_user.id, db)

    # Get all messages in thread grouped by author
    stmt = (
        select(
            Message.author_id,
            User.username,
            User.display_name,
            func.count(Message.id).label("reply_count"),
            func.min(Message.created_at).label("first_reply_at"),
            func.max(Message.created_at).label("last_reply_at"),
        )
        .join(User, Message.author_id == User.id)
        .where(
            Message.thread_id == thread_id,
            Message.deleted_at.is_(None),
        )
        .group_by(Message.author_id, User.username, User.display_name)
        .order_by(desc("reply_count"))
    )

    result = await db.execute(stmt)
    rows = result.all()

    participants = []
    for row in rows:
        participants.append(
            ThreadParticipantResponse(
                user_id=row.author_id,
                username=row.username,
                display_name=row.display_name,
                reply_count=row.reply_count,
                first_reply_at=row.first_reply_at,
                last_reply_at=row.last_reply_at,
            )
        )

    logger.info(f"Retrieved {len(participants)} participants for thread {thread_id}")

    return ThreadParticipantsResponse(
        participants=participants,
        total_count=len(participants),
    )


@router.delete(
    "/threads/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(security)],
)
async def delete_thread(
    thread_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a thread (soft delete).

    Requires:
    - User must be channel admin or thread root message author

    Note: This will soft-delete all messages in the thread.
    """
    # Get thread
    thread = await verify_thread_access(thread_id, current_user.id, db)

    # Get root message to check ownership/admin status
    stmt = select(Message).where(Message.id == thread.root_message_id)
    result = await db.execute(stmt)
    root_message = result.scalar_one_or_none()

    if not root_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread root message not found",
        )

    # Check if user is author or channel admin
    from shared.database import ChannelMember

    stmt = select(ChannelMember).where(
        ChannelMember.channel_id == root_message.channel_id,
        ChannelMember.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()

    is_admin = membership and membership.is_admin
    is_author = root_message.author_id == current_user.id

    if not (is_admin or is_author):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be the thread author or channel admin to delete this thread",
        )

    # Soft delete all messages in thread
    stmt = select(Message).where(Message.thread_id == thread_id)
    result = await db.execute(stmt)
    messages = result.scalars().all()

    now = datetime.now(timezone.utc)
    for message in messages:
        message.deleted_at = now

    await db.commit()

    # Publish thread.deleted event
    await kafka_producer.publish_event(
        topic="threads",
        key=str(thread_id),
        event_type="thread.deleted",
        data={
            "thread_id": str(thread_id),
            "root_message_id": str(thread.root_message_id),
            "channel_id": str(root_message.channel_id),
            "deleted_by": str(current_user.id),
            "deleted_at": now.isoformat(),
        },
    )

    logger.info(f"Thread {thread_id} deleted by user {current_user.id}")
