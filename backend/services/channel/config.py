"""Configuration for Channel Service."""

import os
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Channel Service Settings."""

    # Service info
    service_name: str = "channel"
    port: int = 8003

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://colink:colink_password@localhost:5432/colink",
    )

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Kafka
    kafka_bootstrap_servers: str = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
    )

    # Auth
    auth_proxy_url: str = os.getenv("AUTH_PROXY_URL", "http://localhost:8001")

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # Pagination
    default_page_size: int = 50
    max_page_size: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
