"""Channel management endpoints."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dependencies import get_current_user, get_pagination_params, security, verify_channel_admin
from shared.database import Channel, ChannelMember, ChannelType, Message, User, get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class ChannelCreate(BaseModel):
    """Request model for creating a channel."""

    name: str = Field(..., min_length=1, max_length=80)
    channel_type: ChannelType = ChannelType.public
    description: Optional[str] = Field(None, max_length=250)
    topic: Optional[str] = Field(None, max_length=250)


class ChannelUpdate(BaseModel):
    """Request model for updating a channel."""

    name: Optional[str] = Field(None, min_length=1, max_length=80)
    description: Optional[str] = Field(None, max_length=250)
    topic: Optional[str] = Field(None, max_length=250)


class DMChannelCreate(BaseModel):
    """Request model for creating a DM channel."""

    other_user_id: UUID


class ChannelResponse(BaseModel):
    """Response model for a channel."""

    id: UUID
    name: str
    channel_type: ChannelType
    description: Optional[str] = None
    topic: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Computed fields
    member_count: int = 0
    is_member: bool = False
    is_admin: bool = False
    unread_count: int = 0

    class Config:
        from_attributes = True


class ChannelListResponse(BaseModel):
    """Response model for a list of channels."""

    channels: List[ChannelResponse]
    total: int
    limit: int
    offset: int


# Endpoints
@router.post("/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    channel_data: ChannelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new channel.

    - PUBLIC channels can be joined by anyone
    - PRIVATE channels require invitation
    - Creator automatically becomes first admin
    """
    # Check if channel name already exists (for public/private channels)
    if channel_data.channel_type != ChannelType.direct:
        stmt = select(Channel).where(
            Channel.name == channel_data.name,
            Channel.channel_type.in_([ChannelType.public.value, ChannelType.private.value]),
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Channel with name '{channel_data.name}' already exists",
            )

    # Create channel
    channel = Channel(
        name=channel_data.name,
        channel_type=channel_data.channel_type,
        description=channel_data.description,
        topic=channel_data.topic,
    )

    db.add(channel)
    await db.flush()  # Get channel.id

    # Add creator as first admin member
    member = ChannelMember(
        channel_id=channel.id,
        user_id=current_user.id,
        is_admin=True,
        notifications_enabled=True,
    )
    db.add(member)

    await db.commit()
    await db.refresh(channel)

    logger.info(
        f"Channel created: {channel.id} ({channel.name}) by user {current_user.id}"
    )

    # Import here to avoid circular dependency
    from services.kafka_producer import kafka_producer

    # Publish event to Kafka
    await kafka_producer.publish_channel_event(
        event_type="channel.created",
        channel_data={
            "id": str(channel.id),
            "name": channel.name,
            "channel_type": channel.channel_type,
            "description": channel.description,
            "creator_id": str(current_user.id),
            "created_at": channel.created_at.isoformat(),
        },
        key=str(channel.id),
    )

    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type,
        description=channel.description,
        topic=channel.topic,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        member_count=1,
        is_member=True,
        is_admin=True,
    )


@router.post("/channels/{channel_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_channel_as_read(
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all messages in a channel as read for the current user.

    Updates the last_read_at timestamp to the current time.
    """
    # Get user's channel membership
    stmt = select(ChannelMember).where(
        and_(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel membership not found",
        )

    # Update last_read_at to current time
    membership.last_read_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(f"Channel {channel_id} marked as read by user {current_user.id}")

    return None


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get channel details by ID.

    Returns channel information along with user's membership status.
    """
    # Get channel
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    # Get member count
    stmt = select(ChannelMember).where(ChannelMember.channel_id == channel_id)
    result = await db.execute(stmt)
    members = result.scalars().all()
    member_count = len(members)

    # Check if current user is a member
    user_membership = next(
        (m for m in members if m.user_id == current_user.id), None
    )
    is_member = user_membership is not None
    is_admin = user_membership.is_admin if user_membership else False

    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type,
        description=channel.description,
        topic=channel.topic,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        member_count=member_count,
        is_member=is_member,
        is_admin=is_admin,
    )


@router.get("/channels", response_model=ChannelListResponse)
async def list_user_channels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    pagination: dict = Depends(get_pagination_params),
):
    """List all channels the current user is a member of.

    Includes public, private, and direct message channels.
    """
    # Get user's channel memberships
    stmt = (
        select(Channel)
        .join(ChannelMember, Channel.id == ChannelMember.channel_id)
        .where(ChannelMember.user_id == current_user.id)
        .order_by(desc(Channel.updated_at))
        .limit(pagination["limit"])
        .offset(pagination["offset"])
    )
    result = await db.execute(stmt)
    channels = result.scalars().all()

    # Get total count
    count_stmt = (
        select(Channel)
        .join(ChannelMember, Channel.id == ChannelMember.channel_id)
        .where(ChannelMember.user_id == current_user.id)
    )
    count_result = await db.execute(count_stmt)
    total = len(count_result.scalars().all())

    # Build response
    channel_responses = []
    for channel in channels:
        # Get member count
        member_stmt = select(ChannelMember).where(
            ChannelMember.channel_id == channel.id
        )
        member_result = await db.execute(member_stmt)
        members = member_result.scalars().all()

        # Check if user is admin
        user_membership = next(
            (m for m in members if m.user_id == current_user.id), None
        )
        is_admin = user_membership.is_admin if user_membership else False

        # Calculate unread count
        unread_count = 0
        if user_membership and user_membership.last_read_at:
            # Count messages after last_read_at
            unread_stmt = select(Message).where(
                and_(
                    Message.channel_id == channel.id,
                    Message.created_at > user_membership.last_read_at,
                    Message.author_id != current_user.id,  # Don't count own messages
                    Message.deleted_at.is_(None),  # Don't count deleted messages
                )
            )
            unread_result = await db.execute(unread_stmt)
            unread_count = len(unread_result.scalars().all())
        elif not user_membership or not user_membership.last_read_at:
            # If never read, count all messages except own
            unread_stmt = select(Message).where(
                and_(
                    Message.channel_id == channel.id,
                    Message.author_id != current_user.id,
                    Message.deleted_at.is_(None),
                )
            )
            unread_result = await db.execute(unread_stmt)
            unread_count = len(unread_result.scalars().all())

        channel_responses.append(
            ChannelResponse(
                id=channel.id,
                name=channel.name,
                channel_type=channel.channel_type,
                description=channel.description,
                topic=channel.topic,
                created_at=channel.created_at,
                updated_at=channel.updated_at,
                member_count=len(members),
                is_member=True,
                is_admin=is_admin,
                unread_count=unread_count,
            )
        )

    return ChannelListResponse(
        channels=channel_responses,
        total=total,
        limit=pagination["limit"],
        offset=pagination["offset"],
    )


@router.get("/channels/public/list", response_model=ChannelListResponse)
async def list_public_channels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    pagination: dict = Depends(get_pagination_params),
    search: Optional[str] = Query(None, description="Search channels by name"),
):
    """List all public channels for discovery.

    Can be filtered by search query.
    """
    # Build query
    stmt = select(Channel).where(Channel.channel_type == ChannelType.public.value)

    # Add search filter if provided
    if search:
        stmt = stmt.where(Channel.name.ilike(f"%{search}%"))

    stmt = stmt.order_by(desc(Channel.created_at)).limit(pagination["limit"]).offset(
        pagination["offset"]
    )

    result = await db.execute(stmt)
    channels = result.scalars().all()

    # Get total count
    count_stmt = select(Channel).where(Channel.channel_type == ChannelType.public.value)
    if search:
        count_stmt = count_stmt.where(Channel.name.ilike(f"%{search}%"))
    count_result = await db.execute(count_stmt)
    total = len(count_result.scalars().all())

    # Get user's memberships
    membership_stmt = select(ChannelMember).where(
        ChannelMember.user_id == current_user.id
    )
    membership_result = await db.execute(membership_stmt)
    user_memberships = {m.channel_id: m for m in membership_result.scalars().all()}

    # Build response
    channel_responses = []
    for channel in channels:
        # Get member count
        member_stmt = select(ChannelMember).where(
            ChannelMember.channel_id == channel.id
        )
        member_result = await db.execute(member_stmt)
        member_count = len(member_result.scalars().all())

        # Check if user is member/admin
        membership = user_memberships.get(channel.id)
        is_member = membership is not None
        is_admin = membership.is_admin if membership else False

        channel_responses.append(
            ChannelResponse(
                id=channel.id,
                name=channel.name,
                channel_type=channel.channel_type,
                description=channel.description,
                topic=channel.topic,
                created_at=channel.created_at,
                updated_at=channel.updated_at,
                member_count=member_count,
                is_member=is_member,
                is_admin=is_admin,
            )
        )

    return ChannelListResponse(
        channels=channel_responses,
        total=total,
        limit=pagination["limit"],
        offset=pagination["offset"],
    )


@router.put("/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: UUID,
    channel_update: ChannelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update channel information.

    Only channel admins can update channels.
    """
    # Verify user is admin
    channel = await verify_channel_admin(channel_id, current_user.id, db)

    # Update fields if provided
    if channel_update.name is not None:
        # Check if new name already exists
        stmt = select(Channel).where(
            Channel.name == channel_update.name,
            Channel.id != channel_id,
            Channel.channel_type.in_([ChannelType.public.value, ChannelType.private.value]),
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Channel with name '{channel_update.name}' already exists",
            )

        channel.name = channel_update.name

    if channel_update.description is not None:
        channel.description = channel_update.description

    if channel_update.topic is not None:
        channel.topic = channel_update.topic

    channel.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(channel)

    logger.info(f"Channel updated: {channel.id} by user {current_user.id}")

    # Import here to avoid circular dependency
    from services.kafka_producer import kafka_producer

    # Publish event to Kafka
    await kafka_producer.publish_channel_event(
        event_type="channel.updated",
        channel_data={
            "id": str(channel.id),
            "name": channel.name,
            "description": channel.description,
            "topic": channel.topic,
            "updated_by": str(current_user.id),
            "updated_at": channel.updated_at.isoformat(),
        },
        key=str(channel.id),
    )

    # Get member count for response
    stmt = select(ChannelMember).where(ChannelMember.channel_id == channel_id)
    result = await db.execute(stmt)
    member_count = len(result.scalars().all())

    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type,
        description=channel.description,
        topic=channel.topic,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        member_count=member_count,
        is_member=True,
        is_admin=True,
    )


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Archive/delete a channel.

    Only channel admins can delete channels.
    This performs a soft delete by removing all members.
    """
    # Verify user is admin
    channel = await verify_channel_admin(channel_id, current_user.id, db)

    # Don't allow deleting DM channels
    if channel.channel_type == ChannelType.direct.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete direct message channels",
        )

    # Delete all channel members (cascade will handle this)
    stmt = select(ChannelMember).where(ChannelMember.channel_id == channel_id)
    result = await db.execute(stmt)
    members = result.scalars().all()

    for member in members:
        await db.delete(member)

    # Delete the channel
    await db.delete(channel)
    await db.commit()

    logger.info(f"Channel deleted: {channel_id} by user {current_user.id}")

    # Import here to avoid circular dependency
    from services.kafka_producer import kafka_producer

    # Publish event to Kafka
    await kafka_producer.publish_channel_event(
        event_type="channel.deleted",
        channel_data={
            "id": str(channel_id),
            "name": channel.name,
            "deleted_by": str(current_user.id),
            "deleted_at": datetime.now(timezone.utc).isoformat(),
        },
        key=str(channel_id),
    )


@router.post("/channels/dm", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_dm_channel(
    dm_data: DMChannelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or get a direct message channel between two users.

    This endpoint is idempotent - if a DM channel already exists between
    the two users, it will return the existing channel.
    """
    # Don't allow DM with self
    if dm_data.other_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create DM channel with yourself",
        )

    # Check if other user exists
    stmt = select(User).where(User.id == dm_data.other_user_id)
    result = await db.execute(stmt)
    other_user = result.scalar_one_or_none()

    if not other_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if DM channel already exists between these users
    # A DM channel has both users as members
    stmt = (
        select(Channel)
        .join(ChannelMember, Channel.id == ChannelMember.channel_id)
        .where(
            Channel.channel_type == ChannelType.direct.value,
            ChannelMember.user_id.in_([current_user.id, dm_data.other_user_id]),
        )
        .group_by(Channel.id)
    )
    result = await db.execute(stmt)
    potential_channels = result.scalars().all()

    # Check which channel has both users
    for channel in potential_channels:
        member_stmt = select(ChannelMember).where(
            ChannelMember.channel_id == channel.id
        )
        member_result = await db.execute(member_stmt)
        members = member_result.scalars().all()
        member_ids = {m.user_id for m in members}

        if member_ids == {current_user.id, dm_data.other_user_id}:
            # Found existing DM channel
            logger.info(
                f"Returning existing DM channel: {channel.id} between users {current_user.id} and {dm_data.other_user_id}"
            )

            return ChannelResponse(
                id=channel.id,
                name=channel.name,
                channel_type=channel.channel_type,
                description=channel.description,
                topic=channel.topic,
                created_at=channel.created_at,
                updated_at=channel.updated_at,
                member_count=2,
                is_member=True,
                is_admin=True,
            )

    # Create new DM channel
    # DM channel name format: "dm_<user1_id>_<user2_id>" (sorted for consistency)
    user_ids = sorted([str(current_user.id), str(dm_data.other_user_id)])
    channel_name = f"dm_{user_ids[0]}_{user_ids[1]}"

    channel = Channel(
        name=channel_name,
        channel_type=ChannelType.direct.value,
        description=f"Direct message between {current_user.username} and {other_user.username}",
    )

    db.add(channel)
    await db.flush()

    # Add both users as admin members
    member1 = ChannelMember(
        channel_id=channel.id,
        user_id=current_user.id,
        is_admin=True,
        notifications_enabled=True,
    )
    member2 = ChannelMember(
        channel_id=channel.id,
        user_id=dm_data.other_user_id,
        is_admin=True,
        notifications_enabled=True,
    )

    db.add(member1)
    db.add(member2)

    await db.commit()
    await db.refresh(channel)

    logger.info(
        f"DM channel created: {channel.id} between users {current_user.id} and {dm_data.other_user_id}"
    )

    # Import here to avoid circular dependency
    from services.kafka_producer import kafka_producer

    # Publish event to Kafka
    await kafka_producer.publish_channel_event(
        event_type="channel.created",
        channel_data={
            "id": str(channel.id),
            "name": channel.name,
            "channel_type": channel.channel_type,
            "user_ids": [str(current_user.id), str(dm_data.other_user_id)],
            "created_at": channel.created_at.isoformat(),
        },
        key=str(channel.id),
    )

    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type,
        description=channel.description,
        topic=channel.topic,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        member_count=2,
        is_member=True,
        is_admin=True,
    )
