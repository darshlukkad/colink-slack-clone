"""Common dependencies for Reactions Service."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Channel, ChannelMember, Message, User, get_db

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


async def verify_message_access(
    message_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Message:
    """Verify user has access to a message.

    Returns the message if user has access, raises exception otherwise.
    User must be a member of the channel the message belongs to.
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

    # Don't allow reactions on deleted messages
    if message.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    # Check if user is a member of the channel
    stmt = select(ChannelMember).where(
        ChannelMember.channel_id == message.channel_id,
        ChannelMember.user_id == user_id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this channel",
        )

    return message
