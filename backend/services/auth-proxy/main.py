"""Auth Proxy Service - Main Application Entry Point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.database import close_db, init_db

from .config import settings
from .middleware import auth_middleware
from .routers import auth, health
from prometheus_fastapi_instrumentator import Instrumentator

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Auth Proxy Service...")

    # Initialize database connection
    init_db(settings.database_url, echo=settings.database_echo)
    logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Shutting down Auth Proxy Service...")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="Colink Auth Proxy",
    description="Authentication and authorization proxy for Colink services",
    version="0.1.0",
    lifespan=lifespan,
)

# Expose Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app)
logger.info("Prometheus metrics exposed at /metrics")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add authentication middleware
app.middleware("http")(auth_middleware)

# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.hot_reload,
        log_level=settings.log_level.lower(),
    )
