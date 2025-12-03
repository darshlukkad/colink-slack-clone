"""Main application for Reactions Service."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBearer

from shared.database import close_db, init_db

from .config import settings
from .middleware import AuthMiddleware
from .routers import health_router, reactions_router
from .services.kafka_consumer import kafka_consumer
from .services.kafka_producer import kafka_producer
from prometheus_fastapi_instrumentator import Instrumentator

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("Starting Reactions Service...")

    # Initialize database
    init_db(settings.database_url)
    logger.info("Database initialized")

    # Start Kafka producer
    await kafka_producer.start()
    logger.info("Kafka producer initialized")

    # Start Kafka consumer
    await kafka_consumer.start()
    logger.info("Kafka consumer initialized")

    yield

    # Shutdown
    logger.info("Shutting down Reactions Service...")

    # Stop Kafka consumer
    await kafka_consumer.stop()

    # Stop Kafka producer
    await kafka_producer.stop()

    # Close database
    await close_db()
    logger.info("Database closed")


# Configure security scheme for Swagger UI
security = HTTPBearer()

# Create FastAPI application
app = FastAPI(
    title="Colink Reactions Service",
    description="Emoji reactions service for Colink Slack Clone",
    version=settings.service_version,
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
    },
)

# Expose Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app)
logger.info("Prometheus metrics exposed at /metrics")


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
    allow_origins=settings.get_cors_origins(),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add authentication middleware
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(health_router, tags=["Health"])
app.include_router(reactions_router, tags=["Reactions"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "reactions-service",
        "version": settings.service_version,
        "status": "running",
    }
