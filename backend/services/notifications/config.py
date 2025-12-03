"""Configuration for Notifications Service."""

import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Service settings."""

    # Service info
    service_name: str = "notifications"
    service_version: str = "1.0.0"
    port: int = int(os.getenv("PORT", "8008"))

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://colink:colink_password@localhost:5432/colink",
    )

    # Kafka
    kafka_bootstrap_servers: str = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
    )
    kafka_group_id: str = os.getenv("KAFKA_GROUP_ID", "notifications-service")

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_cache_ttl: int = 300  # 5 minutes

    # Auth
    keycloak_url: str = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
    keycloak_realm: str = os.getenv("KEYCLOAK_REALM", "colink")

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    # Notification defaults
    default_mentions_enabled: bool = True
    default_reactions_enabled: bool = True
    default_replies_enabled: bool = True
    default_direct_messages_enabled: bool = True
    default_channel_updates_enabled: bool = True

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False


settings = Settings()
