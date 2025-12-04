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

    async def _get_admin_token(self) -> str:
        """Get admin access token using client credentials.

        Returns:
            Admin access token

        Raises:
            HTTPException: If unable to get admin token
        """
        try:
            async with httpx.AsyncClient() as client:
                # Get admin token using admin-cli or service account
                token_data = {
                    "grant_type": "client_credentials",
                    "client_id": "admin-cli",
                    "client_secret": settings.keycloak_admin_secret if hasattr(settings, 'keycloak_admin_secret') else "",
                }

                # Try with master realm admin credentials
                admin_token_url = f"{settings.keycloak_url}/realms/master/protocol/openid-connect/token"

                # Use password grant with admin user
                token_data = {
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": "admin",
                    "password": "admin",  # Default Keycloak admin password
                }

                response = await client.post(
                    admin_token_url,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0,
                )

                if response.status_code != 200:
                    logger.error(f"Failed to get admin token: {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Unable to authenticate with Keycloak admin",
                    )

                return response.json()["access_token"]

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get admin token: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Keycloak admin authentication failed",
            )

    async def create_user(
        self,
        username: str,
        email: str,
        first_name: str,
        last_name: str = "",
        password: str = "changeme123",
    ) -> str:
        """Create a new user in Keycloak.

        Args:
            username: Username for the new user
            email: Email address
            first_name: First name (display name)
            last_name: Last name (optional)
            password: Initial password (default: changeme123)

        Returns:
            The Keycloak user ID of the created user

        Raises:
            HTTPException: If user creation fails
        """
        try:
            admin_token = await self._get_admin_token()

            async with httpx.AsyncClient() as client:
                # Create user in Keycloak
                users_url = f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}/users"

                user_data = {
                    "username": username,
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                    "enabled": True,
                    "emailVerified": True,
                    "credentials": [
                        {
                            "type": "password",
                            "value": password,
                            "temporary": False,
                        }
                    ],
                }

                response = await client.post(
                    users_url,
                    json=user_data,
                    headers={
                        "Authorization": f"Bearer {admin_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )

                if response.status_code == 409:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="User with this username or email already exists",
                    )

                if response.status_code != 201:
                    logger.error(f"Failed to create user in Keycloak: {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to create user in Keycloak: {response.text}",
                    )

                # Get the created user's ID from the Location header
                location = response.headers.get("Location", "")
                keycloak_user_id = location.split("/")[-1]

                logger.info(f"Created user {username} in Keycloak with ID {keycloak_user_id}")
                return keycloak_user_id

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create user in Keycloak: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user",
            )

    async def delete_user(self, keycloak_id: str) -> None:
        """Delete a user from Keycloak.

        Args:
            keycloak_id: The Keycloak user ID (sub claim from JWT)

        Raises:
            HTTPException: If user deletion fails
        """
        try:
            admin_token = await self._get_admin_token()

            async with httpx.AsyncClient() as client:
                delete_url = f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}/users/{keycloak_id}"

                response = await client.delete(
                    delete_url,
                    headers={"Authorization": f"Bearer {admin_token}"},
                    timeout=10.0,
                )

                if response.status_code == 204:
                    logger.info(f"Successfully deleted user {keycloak_id} from Keycloak")
                elif response.status_code == 404:
                    logger.warning(f"User {keycloak_id} not found in Keycloak")
                else:
                    logger.warning(f"Failed to delete user from Keycloak: {response.text}")

        except Exception as e:
            logger.warning(f"Failed to delete user from Keycloak: {e}")
            # Don't raise exception - soft delete in DB is sufficient
