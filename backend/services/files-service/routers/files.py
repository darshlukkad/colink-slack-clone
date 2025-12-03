"""File endpoints for Files Service."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import User, get_db

from ..dependencies import get_current_user, get_pagination_params
from ..schemas.files import (
    FileListResponse,
    FileResponse,
    FileUploadResponse,
    SignedUrlRequest,
    SignedUrlResponse,
)
from ..services.file_manager import file_manager
from ..services.minio_service import minio_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# File Upload & Management Endpoints
# ============================================================================


@router.post(
    "/files/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    file: UploadFile = File(...),
    channel_id: Optional[str] = Form(None),
    message_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a file.

    Args:
        file: File to upload
        channel_id: Optional channel ID (for channel attachments)
        message_id: Optional message ID (for message attachments)
        db: Database session
        current_user: Authenticated user

    Returns:
        FileUploadResponse with file metadata
    """
    # Read file data
    file_data = await file.read()

    # Convert string IDs to UUIDs if provided
    channel_uuid = UUID(channel_id) if channel_id else None
    message_uuid = UUID(message_id) if message_id else None

    # Upload file
    try:
        file_record = await file_manager.upload_file(
            db=db,
            file_data=file_data,
            filename=file.filename or "unnamed",
            uploaded_by_id=current_user.id,
            channel_id=channel_uuid,
            message_id=message_uuid,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Classify file
    is_image, is_video, is_document = file_manager.classify_file(
        file_record.original_filename,
        file_record.mime_type,
    )

    return FileUploadResponse(
        id=file_record.id,
        filename=file_record.original_filename,
        url=file_record.url,
        thumbnail_url=file_record.thumbnail_url,
        content_type=file_record.mime_type,
        size=file_record.size_bytes,
        is_image=is_image,
        is_video=is_video,
        is_document=is_document,
        uploaded_by=file_record.uploaded_by_id,
        created_at=file_record.created_at,
    )


@router.get(
    "/files/{file_id}",
    response_model=FileResponse,
)
async def get_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get file metadata by ID.

    Args:
        file_id: File ID
        db: Database session
        current_user: Authenticated user

    Returns:
        FileResponse with file metadata
    """
    file_with_uploader = await file_manager.get_file_with_uploader(db, file_id)

    if not file_with_uploader:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    file_record, uploader = file_with_uploader

    # Classify file
    is_image, is_video, is_document = file_manager.classify_file(
        file_record.original_filename,
        file_record.mime_type,
    )

    return FileResponse(
        id=file_record.id,
        filename=file_record.original_filename,
        original_filename=file_record.original_filename,
        # storage_key=file_record.storage_key,  # Not in schema
        url=file_record.url,
        thumbnail_url=file_record.thumbnail_url,
        content_type=file_record.mime_type,
        size=file_record.size_bytes,
        is_image=is_image,
        is_video=is_video,
        is_document=is_document,
        uploaded_by=file_record.uploaded_by_id,
        uploader_username=uploader.username,
        scan_status=file_record.scan_status,
        created_at=file_record.created_at,
        updated_at=file_record.updated_at,
    )


@router.get(
    "/files/{file_id}/download",
)
async def download_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download file content.

    Args:
        file_id: File ID
        db: Database session
        current_user: Authenticated user

    Returns:
        File content as streaming response
    """
    file_record = await file_manager.get_file(db, file_id)

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Download from MinIO
    try:
        file_data, content_type = minio_service.download_file(file_record.storage_key)
    except Exception as e:
        logger.error(f"Error downloading file {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download file",
        )

    # Return as streaming response
    from io import BytesIO

    return StreamingResponse(
        BytesIO(file_data),
        media_type=file_record.mime_type or content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_record.original_filename}"',
        },
    )


@router.delete(
    "/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a file (soft delete).

    Args:
        file_id: File ID
        db: Database session
        current_user: Authenticated user

    Note: Only file uploader can delete their files
    """
    file_record = await file_manager.get_file(db, file_id)

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Check if user is the uploader
    if file_record.uploaded_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own files",
        )

    # Delete file
    success = await file_manager.delete_file(db, file_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file",
        )


@router.get(
    "/files",
    response_model=FileListResponse,
)
async def list_files(
    channel_id: Optional[UUID] = Query(None),
    message_id: Optional[UUID] = Query(None),
    file_type: Optional[str] = Query(None, regex="^(image|video|document)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List files with optional filters.

    Args:
        channel_id: Filter by channel
        message_id: Filter by message
        file_type: Filter by type (image, video, document)
        page: Page number
        page_size: Items per page
        db: Database session
        current_user: Authenticated user

    Returns:
        FileListResponse with files and pagination info
    """
    files_with_uploaders, total_count = await file_manager.list_files(
        db=db,
        channel_id=channel_id,
        message_id=message_id,
        file_type=file_type,
        page=page,
        page_size=page_size,
    )

    files = []
    for file_record, uploader in files_with_uploaders:
        # Classify file
        is_image, is_video, is_document = file_manager.classify_file(
            file_record.original_filename,
            file_record.mime_type,
        )

        files.append(
            FileResponse(
                id=file_record.id,
                filename=file_record.original_filename,
                original_filename=file_record.original_filename,
                # storage_key=file_record.storage_key,  # Not in schema
                url=file_record.url,
                thumbnail_url=file_record.thumbnail_url,
                content_type=file_record.mime_type,
                size=file_record.size_bytes,
                is_image=is_image,
                is_video=is_video,
                is_document=is_document,
                uploaded_by=file_record.uploaded_by_id,
                uploader_username=uploader.username,
                scan_status=file_record.scan_status,
                created_at=file_record.created_at,
                updated_at=file_record.updated_at,
            )
        )

    total_pages = (total_count + page_size - 1) // page_size
    has_more = page < total_pages

    return FileListResponse(
        files=files,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_more=has_more,
    )


# ============================================================================
# Signed URL Endpoints
# ============================================================================


@router.post(
    "/files/{file_id}/signed-url",
    response_model=SignedUrlResponse,
)
async def generate_signed_url(
    file_id: UUID,
    request: SignedUrlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a temporary signed URL for file access.

    Args:
        file_id: File ID
        request: Signed URL request
        db: Database session
        current_user: Authenticated user

    Returns:
        SignedUrlResponse with temporary URL
    """
    file_record = await file_manager.get_file(db, file_id)

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Generate signed URL
    try:
        signed_url = minio_service.generate_presigned_url(
            file_record.storage_key,
            expiry_seconds=request.expiry_seconds,
        )
    except Exception as e:
        logger.error(f"Error generating signed URL for file {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate signed URL",
        )

    from datetime import datetime, timedelta
    return SignedUrlResponse(
        url=signed_url,
        expires_at=datetime.utcnow() + timedelta(seconds=request.expiry_seconds),
    )


# ============================================================================
# User Files Endpoint
# ============================================================================


@router.get(
    "/users/{user_id}/files",
    response_model=FileListResponse,
)
async def list_user_files(
    user_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all files uploaded by a specific user.

    Args:
        user_id: User ID
        page: Page number
        page_size: Items per page
        db: Database session
        current_user: Authenticated user

    Returns:
        FileListResponse with user's files
    """
    # For now, just return all files (TODO: filter by user_id)
    files_with_uploaders, total_count = await file_manager.list_files(
        db=db,
        page=page,
        page_size=page_size,
    )

    # Filter by user_id manually (TODO: move to file_manager)
    filtered_files = [
        (file_record, uploader)
        for file_record, uploader in files_with_uploaders
        if file_record.uploaded_by_id == user_id
    ]

    files = []
    for file_record, uploader in filtered_files:
        # Classify file
        is_image, is_video, is_document = file_manager.classify_file(
            file_record.original_filename,
            file_record.mime_type,
        )

        files.append(
            FileResponse(
                id=file_record.id,
                filename=file_record.original_filename,
                original_filename=file_record.original_filename,
                # storage_key=file_record.storage_key,  # Not in schema
                url=file_record.url,
                thumbnail_url=file_record.thumbnail_url,
                content_type=file_record.mime_type,
                size=file_record.size_bytes,
                is_image=is_image,
                is_video=is_video,
                is_document=is_document,
                uploaded_by=file_record.uploaded_by_id,
                uploader_username=uploader.username,
                scan_status=file_record.scan_status,
                created_at=file_record.created_at,
                updated_at=file_record.updated_at,
            )
        )

    total_count = len(files)
    total_pages = (total_count + page_size - 1) // page_size
    has_more = page < total_pages

    return FileListResponse(
        files=files,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_more=has_more,
    )
