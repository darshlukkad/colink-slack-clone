"""Routers package for Files Service."""

from .files import router as files_router
from .health import router as health_router

__all__ = ["files_router", "health_router"]
