"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "reactions"}


@router.get("/health/ready")
async def readiness_check():
    """Readiness check endpoint."""
    return {"status": "ready", "service": "reactions"}
