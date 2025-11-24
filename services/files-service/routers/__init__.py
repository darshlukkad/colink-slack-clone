"""Routers package for Files Service."""

from routers.files import router as files_router
from routers.health import router as health_router

__all__ = ["files_router", "health_router"]
