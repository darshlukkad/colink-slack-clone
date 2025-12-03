"""Configuration for Auth Proxy Service."""

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

    # General
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    service_name: str = "auth-proxy"
    port: int = 8001

    # Database
    database_url: str = "postgresql+asyncpg://colink:colink_password@localhost:5432/colink"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 50

    # Keycloak
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "colink"
    keycloak_client_id: str = "web-app"
    keycloak_client_secret: str = "change_me_in_production"

    # JWT
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

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

    @property
    def keycloak_realm_url(self) -> str:
        """Get full Keycloak realm URL."""
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}"

    @property
    def keycloak_jwks_url(self) -> str:
        """Get Keycloak JWKS URL for token verification."""
        return f"{self.keycloak_realm_url}/protocol/openid-connect/certs"

    @property
    def keycloak_token_url(self) -> str:
        """Get Keycloak token endpoint."""
        return f"{self.keycloak_realm_url}/protocol/openid-connect/token"

    @property
    def keycloak_userinfo_url(self) -> str:
        """Get Keycloak userinfo endpoint."""
        return f"{self.keycloak_realm_url}/protocol/openid-connect/userinfo"


# Global settings instance
settings = Settings()
