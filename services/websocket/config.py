"""Configuration settings for WebSocket service."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Server
    port: int = 8009
    environment: str = "development"
    debug: bool = True

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:8080"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:19092"
    kafka_messages_topic: str = "messages"
    kafka_typing_topic: str = "typing"
    kafka_user_status_topic: str = "user_status"
    kafka_reactions_topic: str = "reactions"

    # JWT
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "colink"
    jwt_algorithm: str = "RS256"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def keycloak_realm_url(self) -> str:
        """Get the Keycloak realm URL."""
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}"


settings = Settings()
