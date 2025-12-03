"""Middleware package for Files Service."""

from .auth import AuthMiddleware

__all__ = ["AuthMiddleware"]
