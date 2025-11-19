"""Base database configuration and utilities for Colink.

This module provides:
- SQLAlchemy async engine setup
- Base declarative model class
- Common database session management
- Timestamp mixins and utilities
"""

from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import MetaData, TIMESTAMP
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


# Naming convention for database constraints
# This ensures consistent naming across all migrations
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    Provides:
    - Consistent naming conventions
    - Type checking support
    - Common metadata
    """

    metadata = metadata

    # Allow reflection for type checking
    __allow_unmapped__ = False


class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps to models.

    Usage:
        class MyModel(Base, TimestampMixin):
            __tablename__ = "my_table"
            id: Mapped[int] = mapped_column(primary_key=True)
    """

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# Global async engine and session factory
# These will be initialized by each service on startup
async_engine = None
async_session_factory = None


def init_db(database_url: str, **kwargs) -> None:
    """Initialize the async database engine and session factory.

    Args:
        database_url: PostgreSQL connection URL (must use asyncpg driver)
        **kwargs: Additional arguments passed to create_async_engine

    Example:
        init_db("postgresql+asyncpg://user:pass@localhost/dbname")
    """
    global async_engine, async_session_factory

    # Default engine configuration
    engine_kwargs = {
        "echo": kwargs.pop("echo", False),
        "pool_size": kwargs.pop("pool_size", 20),
        "max_overflow": kwargs.pop("max_overflow", 10),
        "pool_pre_ping": True,  # Verify connections before using
        "pool_recycle": 3600,  # Recycle connections after 1 hour
        **kwargs,
    }

    async_engine = create_async_engine(database_url, **engine_kwargs)

    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database sessions.

    Yields:
        AsyncSession: Database session

    Example:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """Close the database engine and cleanup resources.

    Call this on application shutdown.
    """
    global async_engine, async_session_factory

    if async_engine:
        await async_engine.dispose()
        async_engine = None
        async_session_factory = None
