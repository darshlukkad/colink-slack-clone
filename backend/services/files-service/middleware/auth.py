"""Authentication middleware for Files Service."""

import logging
from typing import Callable
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to extract user_id from X-User-ID header (set by auth proxy)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and extract user_id from header.

        Args:
            request: FastAPI request object
            call_next: Next middleware/route handler

        Returns:
            Response from next handler
        """
        # Extract user_id from header (set by auth proxy)
        user_id_header = request.headers.get("X-User-ID")

        if user_id_header:
            try:
                user_id = UUID(user_id_header)
                request.state.user_id = user_id
                logger.debug(f"Authenticated user: {user_id}")
            except ValueError:
                logger.warning(f"Invalid user_id format: {user_id_header}")
                request.state.user_id = None
        else:
            request.state.user_id = None

        response = await call_next(request)
        return response
