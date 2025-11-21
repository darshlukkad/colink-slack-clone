"""Middleware for Reactions Service."""

import base64
import json
import logging
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate JWT tokens and extract user information.

    This middleware:
    1. Checks for Authorization header
    2. Extracts and validates JWT token
    3. Decodes token to get user ID
    4. Adds user_id to request state
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = [
        "/health",
        "/health/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate authentication."""
        # Skip auth for public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Get Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing Authorization header"},
            )

        # Extract token
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid authentication scheme"},
                )
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid Authorization header format"},
            )

        # Decode JWT token (without verification for now - auth-proxy already verified it)
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
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid token: missing subject"},
                )

            # Add user_id to request state
            request.state.user_id = user_id

            # Continue processing request
            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Token validation failed: {e}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token"},
            )
