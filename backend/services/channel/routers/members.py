"""Channel membership management endpoints."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import (
    get_current_user,
    verify_channel_admin,
    verify_channel_membership,
)
from shared.database import Channel, ChannelMember, ChannelType, User, get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class MemberAdd(BaseModel):
    """Request model for adding a member to a channel."""

    user_id: UUID


class MemberUpdate(BaseModel):
    """Request model for updating a member."""

    is_admin: Optional[bool] = None
    notifications_enabled: Optional[bool] = None


class MemberResponse(BaseModel):
    """Response model for a channel member."""

    user_id: UUID
    username: str
    display_name: Optional[str] = None
    is_admin: bool
    notifications_enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MemberListResponse(BaseModel):
    """Response model for a list of members."""

    members: List[MemberResponse]
    total: int


# Endpoints
@router.post(
    "/channels/{channel_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    channel_id: UUID,
    member_data: MemberAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a member to a channel.

    For PUBLIC channels: User must be a member to add others
    For PRIVATE channels: Only admins can add members
    For DIRECT channels: Cannot add members (only 2 users)
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

    # Check channel type restrictions
    if channel.channel_type == ChannelType.direct.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add members to direct message channels",
        )

    # Verify user has permission to add members
    current_membership = await verify_channel_membership(
        channel_id, current_user.id, db
    )

    if channel.channel_type == ChannelType.private.value and not current_membership.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can add members to private channels",
        )

    # Check if user to add exists
    stmt = select(User).where(User.id == member_data.user_id)
    result = await db.execute(stmt)
    user_to_add = result.scalar_one_or_none()

    if not user_to_add:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if user is already a member
    stmt = select(ChannelMember).where(
        ChannelMember.channel_id == channel_id,
        ChannelMember.user_id == member_data.user_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this channel",
        )

    # Add member
    member = ChannelMember(
        channel_id=channel_id,
        user_id=member_data.user_id,
        is_admin=False,
        notifications_enabled=True,
    )

    db.add(member)
    await db.commit()
    await db.refresh(member)

    logger.info(
        f"Member added: user {member_data.user_id} to channel {channel_id} by {current_user.id}"
    )

    # Import here to avoid circular dependency
    from services.kafka_producer import kafka_producer

    # Publish event to Kafka
    await kafka_producer.publish_channel_event(
        event_type="member.added",
        channel_data={
            "channel_id": str(channel_id),
            "user_id": str(member_data.user_id),
            "added_by": str(current_user.id),
            "added_at": member.created_at.isoformat(),
        },
        key=str(channel_id),
    )

    return MemberResponse(
        user_id=user_to_add.id,
        username=user_to_add.username,
        display_name=user_to_add.display_name,
        is_admin=member.is_admin,
        notifications_enabled=member.notifications_enabled,
        created_at=member.created_at,
    )


@router.get("/channels/{channel_id}/members", response_model=MemberListResponse)
async def list_members(
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all members of a channel.

    User must be a member of the channel to see its members.
    """
    # Verify user is a member
    await verify_channel_membership(channel_id, current_user.id, db)

    # Get all members with user info
    stmt = (
        select(ChannelMember, User)
        .join(User, ChannelMember.user_id == User.id)
        .where(ChannelMember.channel_id == channel_id)
        .order_by(ChannelMember.created_at)
    )
    result = await db.execute(stmt)
    member_user_pairs = result.all()

    # Build response
    members = []
    for member, user in member_user_pairs:
        members.append(
            MemberResponse(
                user_id=user.id,
                username=user.username,
                display_name=user.display_name,
                is_admin=member.is_admin,
                notifications_enabled=member.notifications_enabled,
                created_at=member.created_at,
            )
        )

    return MemberListResponse(
        members=members,
        total=len(members),
    )


@router.put("/channels/{channel_id}/members/{user_id}", response_model=MemberResponse)
async def update_member(
    channel_id: UUID,
    user_id: UUID,
    member_update: MemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a channel member's settings.

    Only admins can change admin status.
    Users can update their own notification settings.
    """
    # Get member to update
    stmt = select(ChannelMember).where(
        ChannelMember.channel_id == channel_id,
        ChannelMember.user_id == user_id,
    )
    result = await db.execute(stmt)
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this channel",
        )

    # Check permissions
    if member_update.is_admin is not None:
        # Only admins can change admin status
        await verify_channel_admin(channel_id, current_user.id, db)
        member.is_admin = member_update.is_admin

    if member_update.notifications_enabled is not None:
        # Users can only update their own notifications, admins can update anyone's
        if user_id != current_user.id:
            await verify_channel_admin(channel_id, current_user.id, db)
        member.notifications_enabled = member_update.notifications_enabled

    await db.commit()
    await db.refresh(member)

    # Get user info
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one()

    logger.info(
        f"Member updated: user {user_id} in channel {channel_id} by {current_user.id}"
    )

    # Import here to avoid circular dependency
    from services.kafka_producer import kafka_producer

    # Publish event to Kafka
    await kafka_producer.publish_channel_event(
        event_type="member.updated",
        channel_data={
            "channel_id": str(channel_id),
            "user_id": str(user_id),
            "is_admin": member.is_admin,
            "updated_by": str(current_user.id),
        },
        key=str(channel_id),
    )

    return MemberResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_admin=member.is_admin,
        notifications_enabled=member.notifications_enabled,
        created_at=member.created_at,
    )


@router.delete(
    "/channels/{channel_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    channel_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from a channel.

    - Users can remove themselves (leave channel)
    - Admins can remove other members
    - Cannot remove members from DM channels
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

    # Cannot remove members from DM channels
    if channel.channel_type == ChannelType.direct.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove members from direct message channels",
        )

    # Get member to remove
    stmt = select(ChannelMember).where(
        ChannelMember.channel_id == channel_id,
        ChannelMember.user_id == user_id,
    )
    result = await db.execute(stmt)
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this channel",
        )

    # Check permissions
    is_self = user_id == current_user.id
    if not is_self:
        # Only admins can remove other members
        await verify_channel_admin(channel_id, current_user.id, db)

    # Delete member
    await db.delete(member)
    await db.commit()

    logger.info(
        f"Member removed: user {user_id} from channel {channel_id} by {current_user.id}"
    )

    # Import here to avoid circular dependency
    from services.kafka_producer import kafka_producer

    # Publish event to Kafka
    await kafka_producer.publish_channel_event(
        event_type="member.removed",
        channel_data={
            "channel_id": str(channel_id),
            "user_id": str(user_id),
            "removed_by": str(current_user.id),
            "is_self_leave": is_self,
        },
        key=str(channel_id),
    )


@router.post(
    "/channels/{channel_id}/join",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def join_channel(
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join a public channel.

    Only works for PUBLIC channels. PRIVATE channels require invitation.
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

    # Only PUBLIC channels can be joined freely
    if channel.channel_type != ChannelType.public.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only join public channels. Private channels require invitation.",
        )

    # Check if already a member
    stmt = select(ChannelMember).where(
        ChannelMember.channel_id == channel_id,
        ChannelMember.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already a member of this channel",
        )

    # Add member
    member = ChannelMember(
        channel_id=channel_id,
        user_id=current_user.id,
        is_admin=False,
        notifications_enabled=True,
    )

    db.add(member)
    await db.commit()
    await db.refresh(member)

    logger.info(f"User {current_user.id} joined channel {channel_id}")

    # Import here to avoid circular dependency
    from services.kafka_producer import kafka_producer

    # Publish event to Kafka
    await kafka_producer.publish_channel_event(
        event_type="member.joined",
        channel_data={
            "channel_id": str(channel_id),
            "user_id": str(current_user.id),
            "created_at": member.created_at.isoformat(),
        },
        key=str(channel_id),
    )

    return MemberResponse(
        user_id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name,
        is_admin=member.is_admin,
        notifications_enabled=member.notifications_enabled,
        created_at=member.created_at,
    )


@router.post(
    "/channels/{channel_id}/leave", status_code=status.HTTP_204_NO_CONTENT
)
async def leave_channel(
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Leave a channel.

    Cannot leave DM channels.
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

    # Cannot leave DM channels
    if channel.channel_type == ChannelType.direct.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot leave direct message channels",
        )

    # Get membership
    stmt = select(ChannelMember).where(
        ChannelMember.channel_id == channel_id,
        ChannelMember.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of this channel",
        )

    # Delete membership
    await db.delete(member)
    await db.commit()

    logger.info(f"User {current_user.id} left channel {channel_id}")

    # Import here to avoid circular dependency
    from services.kafka_producer import kafka_producer

    # Publish event to Kafka
    await kafka_producer.publish_channel_event(
        event_type="member.left",
        channel_data={
            "channel_id": str(channel_id),
            "user_id": str(current_user.id),
            "left_at": datetime.now(timezone.utc).isoformat(),
        },
        key=str(channel_id),
    )
