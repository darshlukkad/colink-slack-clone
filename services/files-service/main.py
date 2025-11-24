"""Files Service - FastAPI application for file upload, download, and management."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from middleware import AuthMiddleware
from routers import files_router, health_router
from services.kafka_producer import kafka_producer
from services.minio_service import minio_service

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
)

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
