"""Configuration for Reactions Service."""

import os
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Service info
    service_name: str = "reactions"
    service_version: str = "1.0.0"
    port: int = int(os.getenv("PORT", "8006"))
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://colink:colink_password@localhost:5432/colink",
    )

    # Kafka
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka_group_id: str = f"{service_name}-service"

    # CORS
    cors_origins: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8000,https://colink.dev",
    )
    cors_allow_credentials: bool = True

    def get_cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False


settings = Settings()
