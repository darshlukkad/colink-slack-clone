"""Configuration for Files Service."""

import os
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Service
    service_name: str = "files-service"
    service_version: str = "1.0.0"
    port: int = int(os.getenv("PORT", "8007"))
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://colink:colink_password@postgres:5432/colink",
    )

    # MinIO/S3
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "minio:9000")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "colink")
    minio_thumbnails_bucket: str = os.getenv("MINIO_THUMBNAILS_BUCKET", "colink-thumbnails")
    minio_secure: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    minio_public_endpoint: str = os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000")

    # File Upload Settings
    max_file_size: int = int(os.getenv("MAX_FILE_SIZE", "52428800"))  # 50MB
    allowed_extensions: List[str] = os.getenv(
        "ALLOWED_EXTENSIONS",
        "png,jpg,jpeg,gif,webp,pdf,doc,docx,txt,csv,xlsx,mp4,webm,mov",
    ).split(",")

    # Image Settings
    thumbnail_size: int = int(os.getenv("THUMBNAIL_SIZE", "300"))
    image_extensions: List[str] = ["png", "jpg", "jpeg", "gif", "webp"]
    video_extensions: List[str] = ["mp4", "webm", "mov", "avi"]
    document_extensions: List[str] = ["pdf", "doc", "docx", "txt", "csv", "xlsx", "xls"]

    # Kafka
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
    kafka_topic: str = os.getenv("KAFKA_TOPIC", "files")
    kafka_group_id: str = os.getenv("KAFKA_GROUP_ID", "files-service")

    # CORS
    cors_origins: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8000,https://colink.dev",
    )
    cors_allow_credentials: bool = True

    # Keycloak
    keycloak_url: str = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
    keycloak_realm: str = os.getenv("KEYCLOAK_REALM", "colink")
    keycloak_client_id: str = os.getenv("KEYCLOAK_CLIENT_ID", "web-app")

    def get_cors_origins(self) -> List[str]:
        """Parse CORS origins from environment."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
