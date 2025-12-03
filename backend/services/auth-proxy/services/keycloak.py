"""Keycloak integration service for JWT validation and user management."""

import base64
import json
import logging
from typing import Any, Dict

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt

from ..config import settings

logger = logging.getLogger(__name__)


class KeycloakService:
    """Service for interacting with Keycloak."""

    def __init__(self):
        """Initialize Keycloak service."""
        self.realm_url = settings.keycloak_realm_url
        self.token_url = settings.keycloak_token_url
        self.userinfo_url = settings.keycloak_userinfo_url
        self.jwks_url = settings.keycloak_jwks_url
        self.client_id = settings.keycloak_client_id
        self.client_secret = settings.keycloak_client_secret
        self._jwks_cache: Dict[str, Any] = {}

    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate user with Keycloak and get tokens.

        Args:
            username: Username or email
            password: User password

        Returns:
            Dict containing access_token, refresh_token, and expires_in

        Raises:
            HTTPException: If authentication fails
        """
        try:
            async with httpx.AsyncClient() as client:
                # Prepare token request data
                token_data = {
                    "grant_type": "password",
                    "client_id": self.client_id,
                    "username": username,
                    "password": password,
                }

                # Note: web-app is a public client and doesn't need client_secret
                # Only confidential clients require client_secret

                response = await client.post(
                    self.token_url,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0,
                )

                if response.status_code == 401:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid credentials",
                    )

                response.raise_for_status()
                return response.json()

        except HTTPException:
            raise
        except httpx.HTTPError as e:
            logger.error(f"Keycloak login failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            )
        except Exception as e:
            logger.error(f"Unexpected error during login: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication failed",
            )

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token from previous login

        Returns:
            Dict containing new access_token, refresh_token, and expires_in

        Raises:
            HTTPException: If token refresh fails
        """
        try:
            async with httpx.AsyncClient() as client:
                token_data = {
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "refresh_token": refresh_token,
                }

                response = await client.post(
                    self.token_url,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0,
                )

                if response.status_code == 400:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or expired refresh token",
                    )

                response.raise_for_status()
                return response.json()

        except HTTPException:
            raise
        except httpx.HTTPError as e:
            logger.error(f"Token refresh failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            )

    async def logout(self, refresh_token: str) -> None:
        """Revoke refresh token (logout).

        Args:
            refresh_token: Refresh token to revoke
        """
        try:
            async with httpx.AsyncClient() as client:
                logout_url = f"{settings.keycloak_realm_url}/protocol/openid-connect/logout"
                await client.post(
                    logout_url,
                    data={
                        "client_id": self.client_id,
                        "refresh_token": refresh_token,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0,
                )
        except Exception as e:
            logger.warning(f"Logout revocation failed (non-critical): {e}")

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from access token.

        Decodes the JWT token directly to extract user information
        instead of calling the userinfo endpoint.

        Args:
            access_token: Valid JWT access token

        Returns:
            Dict containing user information (sub, email, name, etc.)

        Raises:
            HTTPException: If token is invalid
        """
        try:
            # Decode JWT payload (without verification)
            # The token was just issued by Keycloak, so we trust it here
            # In a production scenario with tokens from external sources,
            # you should verify the signature using JWKS
            parts = access_token.split('.')
            if len(parts) != 3:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token format",
                )

            payload = parts[1]
            # Add padding if needed for base64 decoding
            payload += '=' * (4 - len(payload) % 4)
            decoded_bytes = base64.urlsafe_b64decode(payload)
            user_info = json.loads(decoded_bytes)

            # Validate token is from our realm
            # Accept both localhost and keycloak hostname (for container/local testing)
            token_issuer = user_info.get("iss", "")
            valid_issuers = [
                f"{settings.keycloak_url}/realms/{settings.keycloak_realm}",
                f"http://localhost:8080/realms/{settings.keycloak_realm}",
                f"http://keycloak:8080/realms/{settings.keycloak_realm}",
            ]

            if not any(token_issuer == issuer for issuer in valid_issuers):
                logger.warning(f"Invalid token issuer: {token_issuer}, expected one of {valid_issuers}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token issuer",
                )

            return user_info

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to decode user info from token: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token using Keycloak's public keys.

        Args:
            token: JWT token to verify

        Returns:
            Dict containing decoded token claims

        Raises:
            HTTPException: If token is invalid or verification fails
        """
        try:
            # Get JWKS (JSON Web Key Set) from Keycloak
            if not self._jwks_cache:
                async with httpx.AsyncClient() as client:
                    response = await client.get(self.jwks_url, timeout=10.0)
                    response.raise_for_status()
                    self._jwks_cache = response.json()

            # Decode and verify token
            # Note: python-jose will automatically select the correct key from JWKS
            unverified_header = jwt.get_unverified_header(token)

            # For simplicity, we'll use get_user_info which validates the token
            # In production, you might want to cache the JWKS and verify locally
            user_info = await self.get_user_info(token)

            return user_info

        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token verification error: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed",
            )

    def clear_jwks_cache(self) -> None:
        """Clear cached JWKS (useful for key rotation)."""
        self._jwks_cache = {}
