"""Common dependencies for Notifications Service."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import User, get_db

# Security scheme for Swagger UI
security = HTTPBearer()


async def get_current_user_id(request: Request) -> UUID:
    """Get current user ID from authentication middleware.

    This is set by the auth-proxy service after validating the JWT token.
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
