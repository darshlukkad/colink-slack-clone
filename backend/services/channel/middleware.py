"""Middleware for Channel Service."""

import base64
import json
import logging
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to extract user information from JWT token.

    The auth-proxy service has already validated the token,
    so we just need to decode it and extract user info.
    """

    # Public paths that don't require authentication
    PUBLIC_PATHS = ["/health", "/health/ready", "/docs", "/redoc", "/openapi.json"]

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request and extract user info from JWT."""
        # Allow public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Allow OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
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

        # Decode JWT payload (without verification since auth-proxy already verified)
        try:
            # JWT structure: header.payload.signature
            parts = token.split(".")
            if len(parts) != 3:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid token format"},
                )

            # Decode payload (base64url)
            payload = parts[1]
            # Add padding if needed
            payload += "=" * (4 - len(payload) % 4)
            decoded_bytes = base64.urlsafe_b64decode(payload)
            payload_data = json.loads(decoded_bytes)

            # Extract user ID from 'sub' claim
            user_id = payload_data.get("sub")
            if not user_id:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Missing user ID in token"},
                )

            # Store user_id in request state for use in dependencies
            request.state.user_id = user_id

        except Exception as e:
            logger.error(f"Error decoding JWT: {e}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid token"},
            )

        response = await call_next(request)
        return response
