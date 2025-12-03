"""Common dependencies for Threads Service."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Channel, ChannelMember, Message, Thread, User, get_db

# Security scheme for Swagger UI
security = HTTPBearer()


async def get_current_user_id(request: Request) -> UUID:
    """Get current user ID from authentication middleware.

    This is set by the AuthMiddleware after validating the JWT token.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return UUID(user_id)


async def get_current_user(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from database."""
    # The user_id from JWT is actually the keycloak_id
    stmt = select(User).where(User.keycloak_id == str(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


async def verify_channel_access(
    channel_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Channel:
    """Verify user has access to a channel.

    Returns the channel if user is a member, raises exception otherwise.
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

    # Check if user is a member of the channel
    stmt = select(ChannelMember).where(
        ChannelMember.channel_id == channel_id,
        ChannelMember.user_id == user_id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this channel",
        )

    return channel


async def verify_thread_access(
    thread_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Thread:
    """Verify user has access to a thread.

    Returns the thread if user has access, raises exception otherwise.
    User must be a member of the channel the thread belongs to.
    """
    # Get thread with root message
    stmt = select(Thread).where(Thread.id == thread_id)
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    # Get root message to find channel
    stmt = select(Message).where(Message.id == thread.root_message_id)
    result = await db.execute(stmt)
    root_message = result.scalar_one_or_none()

    if not root_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread root message not found",
        )

    # Verify channel access
    await verify_channel_access(root_message.channel_id, user_id, db)

    return thread


def get_pagination_params(
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Get pagination parameters.

    Args:
        limit: Number of items to return (default 50, max 100)
        offset: Number of items to skip (default 0)

    Returns:
        Dict with pagination parameters
    """
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100

    if offset < 0:
        offset = 0

    return {
        "limit": limit,
        "offset": offset,
    }
