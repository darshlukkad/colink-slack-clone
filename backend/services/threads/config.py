"""Configuration for Threads Service."""

import os
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service
    service_name: str = "threads-service"
    service_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://colink:colink_password@localhost:5432/colink"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_message_topic: str = "messages"
    kafka_thread_topic: str = "threads"

    # Auth
    auth_proxy_url: str = "http://localhost:8001"
    jwt_algorithm: str = "RS256"
    jwt_public_key_url: str = "http://keycloak:8080/realms/colink/protocol/openid-connect/certs"

    # Pagination
    default_page_size: int = 50
    max_page_size: int = 100

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:8000"
    cors_allow_credentials: bool = True

    # Rate Limiting
    rate_limit_per_minute: int = 100
    rate_limit_burst: int = 200

    # Development
    hot_reload: bool = True

    def get_cors_origins(self) -> List[str]:
        """Parse and return CORS origins as list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Global settings instance
settings = Settings()
