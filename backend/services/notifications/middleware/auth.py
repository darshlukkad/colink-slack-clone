"""Authentication middleware for notifications service."""

import base64
import json
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to decode JWT tokens and attach user_id to request.

    This middleware decodes the JWT without verification as it's assumed
    the token was already verified by the auth-proxy service.
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = [
        "/health",
        "/health/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
    ]

    async def dispatch(self, request: Request, call_next):
        """Process request and extract user information from JWT."""
        # Skip auth for public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Get Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning("Missing Authorization header")
            return Response(
                content='{"detail":"Missing Authorization header"}',
                status_code=401,
                media_type="application/json",
            )

        # Extract token
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                logger.warning("Invalid authentication scheme")
                return Response(
                    content='{"detail":"Invalid authentication scheme"}',
                    status_code=401,
                    media_type="application/json",
                )
        except ValueError:
            logger.warning("Invalid Authorization header format")
            return Response(
                content='{"detail":"Invalid Authorization header format"}',
                status_code=401,
                media_type="application/json",
            )

        # Decode JWT token (without verification - auth-proxy already verified it)
        try:
            # JWT structure: header.payload.signature
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid JWT structure")

            # Decode payload (add padding if needed)
            payload = parts[1]
            payload += "=" * (4 - len(payload) % 4)
            decoded_bytes = base64.urlsafe_b64decode(payload)
            payload_data = json.loads(decoded_bytes)

            # Extract user ID from 'sub' claim
            user_id = payload_data.get("sub")
            if not user_id:
                logger.warning("Missing subject in token")
                return Response(
                    content='{"detail":"Invalid token: missing subject"}',
                    status_code=401,
                    media_type="application/json",
                )

            # Add user_id to request state
            request.state.user_id = user_id
            logger.info(f"User authenticated: {user_id}")

            # Continue processing request
            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Token decoding failed: {e}", exc_info=True)
            return Response(
                content='{"detail":"Invalid or expired token"}',
                status_code=401,
                media_type="application/json",
            )
