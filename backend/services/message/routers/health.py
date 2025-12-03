"""Health check endpoints for Message Service."""

from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint.

    Returns service status without checking dependencies.
    """
    return {
        "status": "healthy",
        "service": "message-service",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check endpoint.

    Checks if service is ready to accept requests by verifying:
    - Database connectivity
    """
    try:
        # Check database connection
        result = await db.execute(text("SELECT 1"))
        result.scalar()

        return {
            "status": "ready",
            "service": "message-service",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "status": "not_ready",
            "service": "message-service",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
