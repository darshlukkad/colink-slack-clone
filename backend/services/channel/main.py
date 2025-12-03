"""Main application for Channel Service."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from config import settings
from middleware import AuthMiddleware
from routers import channels, health, members
from services.kafka_producer import kafka_producer
from shared.database import close_db, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Channel Service...")

    # Initialize database
    init_db(settings.database_url)
    logger.info("Database initialized")

    # Start Kafka producer
    try:
        await kafka_producer.start()
    except Exception as e:
        logger.error(f"Failed to start Kafka producer: {e}")
        logger.warning("Continuing without Kafka - events will not be published")

    logger.info("Channel Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Channel Service...")

    # Stop Kafka producer
    await kafka_producer.stop()

    # Close database connections
    await close_db()

    logger.info("Channel Service shut down successfully")


# Create FastAPI app
app = FastAPI(
    title="Colink Channel Service",
    description="Microservice for managing channels and memberships",
    version="0.1.0",
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
    },
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
    }

    # Apply security globally to all endpoints except health
    for path, path_item in openapi_schema["paths"].items():
        if not path.startswith("/health"):
            for operation in path_item.values():
                if isinstance(operation, dict):
                    operation["security"] = [{"HTTPBearer": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore

# Add authentication middleware FIRST (middleware runs in reverse order)
app.add_middleware(AuthMiddleware)

# Add CORS middleware (runs first due to reverse order)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(channels.router, tags=["Channels"])
app.include_router(members.router, tags=["Members"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "channel",
        "version": "0.1.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
    )
