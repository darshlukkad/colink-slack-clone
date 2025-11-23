"""Notifications Service - Main application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBearer

from shared.database.base import close_db, init_db

from .config import settings
from .middleware.auth import AuthMiddleware
from .routers import health, notifications
from .services.kafka_consumer import kafka_consumer
from .services.kafka_producer import kafka_producer
from .services.notification_manager import notification_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info(f"Starting {settings.service_name} service v{settings.service_version}")

    # Initialize database
    init_db(settings.database_url)
    logger.info("Database initialized")

    # Initialize Redis
    await notification_manager.init_redis()

    # Start Kafka producer and consumer
    await kafka_producer.start()
    await kafka_consumer.start()

    yield

    # Shutdown
    logger.info("Shutting down...")
    await kafka_consumer.stop()
    await kafka_producer.stop()
    await notification_manager.close_redis()
    await close_db()


# Security scheme for Swagger UI
security = HTTPBearer()

# Create FastAPI app
app = FastAPI(
    title="Colink Notifications Service",
    description="Manages user notifications and preferences",
    version=settings.service_version,
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)


def custom_openapi():
    """Customize OpenAPI schema to add security."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add security scheme
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}

    openapi_schema["components"]["securitySchemes"]["HTTPBearer"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Enter your JWT token from the auth service login endpoint",
    }

    # Apply security globally to all endpoints except health
    for path, path_item in openapi_schema["paths"].items():
        if not path.startswith("/health"):
            for operation in path_item.values():
                if isinstance(operation, dict):
                    operation["security"] = [{"HTTPBearer": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add authentication middleware
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(health.router)
app.include_router(notifications.router)

logger.info(f"Notifications service configured on port {settings.port}")
