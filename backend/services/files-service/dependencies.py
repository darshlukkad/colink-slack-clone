"""Dependencies for Files Service."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import User, get_db

logger = logging.getLogger(__name__)


async def get_current_user_id(request: Request) -> UUID:
    """Get current user ID from request state (set by auth middleware).

    Args:
        request: FastAPI request object

    Returns:
        User ID

    Raises:
        HTTPException: If user is not authenticated
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user_id


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user.

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: If user is not authenticated or not found
    """
    user_id = await get_current_user_id(request)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Get user from database (user_id from JWT is actually keycloak_id)
    stmt = select(User).where(User.keycloak_id == str(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def get_pagination_params(
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, int]:
    """Get pagination parameters.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Tuple of (limit, offset)
    """
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    offset = (page - 1) * page_size
    return page_size, offset
