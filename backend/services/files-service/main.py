"""Files Service - FastAPI application for file upload, download, and management."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .middleware.auth_jwt import AuthMiddleware
from .routers import files_router, health_router
from .services.kafka_producer import kafka_producer
from .services.minio_service import minio_service
from prometheus_fastapi_instrumentator import Instrumentator


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Files Service",
    description="File upload, download, and management service for Colink",
    version="1.0.0",
    swagger_ui_init_oauth={
        "clientId": settings.keycloak_client_id,
        "appName": "Files Service",
        "usePkceWithAuthorizationCodeGrant": True,
    },
)

# Expose Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app)
logger.info("Prometheus metrics exposed at /metrics")


def custom_openapi():
    """Customize OpenAPI schema to include security."""
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Ensure components exists
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/auth",
                    "tokenUrl": f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token",
                    "scopes": {
                        "openid": "OpenID Connect",
                        "profile": "User profile",
                        "email": "Email address",
                    },
                }
            },
        },
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },
    }

    # Apply security globally to all endpoints except health
    for path, path_item in openapi_schema["paths"].items():
        if "/health" not in path:  # Exclude health endpoint
            for method in path_item.values():
                if isinstance(method, dict) and "security" not in method:
                    method["security"] = [
                        {"BearerAuth": []},
                        {"OAuth2PasswordBearer": ["openid", "profile", "email"]},
                    ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(health_router, tags=["Health"])
app.include_router(files_router, prefix="/api/v1", tags=["Files"])


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting Files Service...")

    # Initialize database
    try:
        from shared.database import init_db
        init_db(settings.database_url)
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Initialize MinIO buckets
    try:
        minio_service.initialize_buckets()
        logger.info("MinIO buckets initialized")
    except Exception as e:
        logger.error(f"Failed to initialize MinIO buckets: {e}")
        raise

    # Start Kafka producer
    try:
        await kafka_producer.start()
        logger.info("Kafka producer started")
    except Exception as e:
        logger.error(f"Failed to start Kafka producer: {e}")
        raise

    logger.info("Files Service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Files Service...")

    # Stop Kafka producer
    try:
        await kafka_producer.stop()
        logger.info("Kafka producer stopped")
    except Exception as e:
        logger.error(f"Error stopping Kafka producer: {e}")

    logger.info("Files Service shut down")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
    )
