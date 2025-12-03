"""Health check endpoints for Channel Service."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "channel"}


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check with database connectivity test."""
    try:
        # Test database connection
        await db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "service": "channel",
            "database": "connected",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "not_ready",
            "service": "channel",
            "database": "disconnected",
            "error": str(e),
        }
