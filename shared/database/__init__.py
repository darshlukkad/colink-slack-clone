"""Shared database components for Colink services.

This package provides:
- Base SQLAlchemy model class
- Database session management
- Common models used across services
- Timestamp mixins
"""

from shared.database.base import Base, TimestampMixin, close_db, get_db, init_db
from shared.database.models import User, UserRole, UserStatus

__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    # Database functions
    "init_db",
    "get_db",
    "close_db",
    # Models
    "User",
    "UserStatus",
    "UserRole",
]
