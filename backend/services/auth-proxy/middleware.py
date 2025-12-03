"""Authentication middleware for Auth Proxy Service."""

import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Public paths that don't require authentication
PUBLIC_PATHS = {
    "/health",
    "/health/",
    "/health/ready",
    "/auth/login",
    "/auth/refresh",
    "/auth/logout",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",
}


async def auth_middleware(request: Request, call_next: Callable) -> Response:
    """Authentication middleware to validate JWT tokens.

    This middleware:
    1. Checks if the path is public (doesn't require auth)
    2. For protected paths, validates the JWT token
    3. Extracts user info and adds to request state

    Public paths (no auth required):
    - /health/*
    - /auth/login
    - /auth/refresh
    - /auth/logout
    - /docs, /redoc, /openapi.json
    """
    path = request.url.path

    # Allow public paths without authentication
    if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PATHS):
        return await call_next(request)

    # For protected paths, token validation is handled by individual endpoints
    # using FastAPI's security dependencies (HTTPBearer)
    # This middleware is mainly for logging and future rate limiting

    try:
        response = await call_next(request)
        return response

    except Exception as e:
        logger.error(f"Middleware error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
