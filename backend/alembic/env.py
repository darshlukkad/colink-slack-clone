"""Alembic migration environment configuration for Colink.

This module configures Alembic to work with:
- Multiple services with separate database schemas
- Async PostgreSQL (asyncpg) support
- Environment variable configuration
- Auto-formatting with Black
"""

import asyncio
import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Load environment variables from .env file
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models from shared/database/models.py
# This will be created in the next step
# For now, we'll set target_metadata to None and update it later
try:
    from shared.database.models import Base

    target_metadata = Base.metadata
except ImportError:
    # Models not created yet, use None
    target_metadata = None

# Override sqlalchemy.url from environment variable
database_url = os.getenv("DATABASE_URL", "postgresql://colink:colink_password@localhost:5432/colink")
if database_url and config.get_main_option("sqlalchemy.url") is None:
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # Detect column type changes
        compare_server_default=True,  # Detect default value changes
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # Detect column type changes
        compare_server_default=True,  # Detect default value changes
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Use async database URL if available
    database_url_sync = config.get_main_option("sqlalchemy.url")

    # Convert sync URL to async URL for asyncpg
    if database_url_sync and "postgresql://" in database_url_sync:
        database_url_async = database_url_sync.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
    else:
        database_url_async = os.getenv(
            "ASYNC_DATABASE_URL",
            "postgresql+asyncpg://colink:colink_password@localhost:5432/colink",
        )

    # Create async configuration
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url_async

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
