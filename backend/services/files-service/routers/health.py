"""Health check endpoint for Files Service."""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        Dict with service status
    """
    return {
        "status": "healthy",
        "service": "files-service",
    }
