"""Pydantic schemas for Files service."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# File Schemas
# ============================================================================


class FileUploadResponse(BaseModel):
    """Response after uploading a file."""

    id: UUID
    filename: str
    url: str
    thumbnail_url: Optional[str] = None
    content_type: str
    size: int
    is_image: bool = False
    is_video: bool = False
    is_document: bool = False
    uploaded_by: UUID
    created_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True


class FileResponse(BaseModel):
    """Complete file information response."""

    id: UUID
    filename: str
    original_filename: str
    url: str
    thumbnail_url: Optional[str] = None
    content_type: str
    size: int
    is_image: bool = False
    is_video: bool = False
    is_document: bool = False
    channel_id: Optional[UUID] = None
    message_id: Optional[UUID] = None
    uploaded_by: UUID
    uploader_username: Optional[str] = None
    uploader_display_name: Optional[str] = None
    scan_status: Optional[str] = "pending"
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True


class FileListResponse(BaseModel):
    """Response for file listing."""

    files: List[FileResponse]
    total_count: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class SignedUrlRequest(BaseModel):
    """Request to generate signed URL."""

    expiry_seconds: int = Field(default=3600, ge=1, le=86400, description="URL expiry in seconds (max 24 hours)")


class SignedUrlResponse(BaseModel):
    """Response with signed URL."""

    url: str
    expires_at: datetime


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    service: str = "files-service"
    minio_connected: bool = False
    timestamp: datetime
