"""Authentication endpoints for Auth Proxy Service."""

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import User, UserRole, UserStatus, get_db

from ..config import settings
from ..services.keycloak import KeycloakService

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()


# ============================================================================
# Request/Response Models
# ============================================================================


class LoginRequest(BaseModel):
    """Login request with username/email and password."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response from authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


class UserInfo(BaseModel):
    """User information from token."""

    id: str
    username: str
    email: str  # Using str instead of EmailStr to allow .local domains in development
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: UserRole
    status: UserStatus


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Login with username/email and password.

    This endpoint:
    1. Authenticates with Keycloak
    2. Gets user info from Keycloak
    3. Creates or updates user in our database
    4. Returns tokens
    """
    try:
        # Initialize Keycloak service
        keycloak = KeycloakService()

        # Authenticate with Keycloak
        token_data = await keycloak.login(credentials.username, credentials.password)

        # Get user info from Keycloak
        user_info = await keycloak.get_user_info(token_data["access_token"])

        # Create or update user in database
        stmt = select(User).where(User.keycloak_id == user_info["sub"])
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Update existing user
            user.email = user_info.get("email", user.email)
            user.username = user_info.get("preferred_username", user.username)
            user.display_name = user_info.get("name", user.display_name)
            user.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None).replace(tzinfo=None)  # Remove timezone for DB compatibility
        else:
            # Create new user
            # Note: created_at and updated_at will be set by database defaults
            user = User(
                keycloak_id=user_info["sub"],
                email=user_info.get("email", ""),
                username=user_info.get("preferred_username", credentials.username),
                display_name=user_info.get("name"),
                status=UserStatus.ACTIVE,
                role=UserRole.MEMBER,
                last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None).replace(tzinfo=None),  # Remove timezone for DB compatibility
            )
            db.add(user)

        await db.commit()
        logger.info(f"User {user.username} logged in successfully")

        return TokenResponse(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data["expires_in"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed",
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """Refresh access token using refresh token."""
    try:
        keycloak = KeycloakService()
        token_data = await keycloak.refresh_token(request.refresh_token)

        return TokenResponse(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", request.refresh_token),
            expires_in=token_data["expires_in"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed",
        )


@router.post("/logout")
async def logout(request: RefreshTokenRequest):
    """Logout by revoking the refresh token."""
    try:
        keycloak = KeycloakService()
        await keycloak.logout(request.refresh_token)

        return {"message": "Logged out successfully"}

    except Exception as e:
        logger.error(f"Logout failed: {e}", exc_info=True)
        # Don't fail logout even if revocation fails
        return {"message": "Logged out"}


@router.get("/me", response_model=UserInfo)
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(security),
):
    """Get current user information from token.

    This endpoint validates the JWT token and returns user info.
    """
    try:
        # Extract token from Authorization header
        access_token = token.credentials

        # Validate token with Keycloak
        keycloak = KeycloakService()
        user_info = await keycloak.get_user_info(access_token)

        # Get user from database
        stmt = select(User).where(User.keycloak_id == user_info["sub"])
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Update last seen
        user.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

        return UserInfo(
            id=str(user.id),
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            role=user.role,
            status=user.status,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
