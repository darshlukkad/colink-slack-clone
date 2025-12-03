"""File manager - business logic for file operations."""

import logging
import mimetypes
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import File, User

from ..config import settings
from .kafka_producer import kafka_producer
from .minio_service import minio_service
from .thumbnail_service import thumbnail_service

logger = logging.getLogger(__name__)


class FileManager:
    """Manages file operations."""

    def __init__(self):
        """Initialize file manager."""
        self.max_file_size = settings.max_file_size
        self.allowed_extensions = settings.allowed_extensions

    def validate_file(self, filename: str, file_size: int) -> Tuple[bool, Optional[str]]:
        """Validate file upload.

        Args:
            filename: Original filename
            file_size: File size in bytes

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file size
        if file_size > self.max_file_size:
            max_mb = self.max_file_size / (1024 * 1024)
            return False, f"File size exceeds maximum allowed size of {max_mb:.1f}MB"

        # Check file extension
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in self.allowed_extensions:
            return False, f"File type .{ext} is not allowed"

        return True, None

    def generate_storage_filename(self, original_filename: str) -> str:
        """Generate unique filename for storage.

        Args:
            original_filename: Original filename

        Returns:
            Unique filename with extension
        """
        ext = original_filename.rsplit(".", 1)[-1] if "." in original_filename else "bin"
        return f"{uuid.uuid4()}.{ext}"

    def get_content_type(self, filename: str) -> str:
        """Get MIME type for file.

        Args:
            filename: Filename

        Returns:
            MIME type string
        """
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"

    def classify_file(self, filename: str, content_type: str) -> Tuple[bool, bool, bool]:
        """Classify file type.

        Args:
            filename: Filename
            content_type: MIME type

        Returns:
            Tuple of (is_image, is_video, is_document)
        """
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        is_image = ext in settings.image_extensions or content_type.startswith("image/")
        is_video = ext in settings.video_extensions or content_type.startswith("video/")
        is_document = ext in settings.document_extensions or content_type.startswith("application/")

        return is_image, is_video, is_document

    async def upload_file(
        self,
        db: AsyncSession,
        file_data: bytes,
        filename: str,
        uploaded_by_id: UUID,
        channel_id: Optional[UUID] = None,
        message_id: Optional[UUID] = None,
    ) -> File:
        """Upload file and create database record.

        Args:
            db: Database session
            file_data: File content
            filename: Original filename
            uploaded_by_id: User who uploaded the file
            channel_id: Associated channel (optional)
            message_id: Associated message (optional)

        Returns:
            File model instance
        """
        # Validate file
        is_valid, error_msg = self.validate_file(filename, len(file_data))
        if not is_valid:
            raise ValueError(error_msg)

        # Generate storage filename
        storage_filename = self.generate_storage_filename(filename)
        content_type = self.get_content_type(filename)
        is_image, is_video, is_document = self.classify_file(filename, content_type)

        # Upload to MinIO
        url = minio_service.upload_file(
            file_data=file_data,
            object_name=storage_filename,
            content_type=content_type,
        )

        # Generate thumbnail for images
        thumbnail_url = None
        if is_image and thumbnail_service.is_supported_image(filename):
            thumbnail_data = thumbnail_service.generate_thumbnail(file_data)
            if thumbnail_data:
                thumb_filename = f"thumb_{storage_filename}"
                thumbnail_url = minio_service.upload_file(
                    file_data=thumbnail_data,
                    object_name=thumb_filename,
                    content_type="image/jpeg",
                    bucket=settings.minio_thumbnails_bucket,
                )

        # Create database record
        file_record = File(
            id=uuid.uuid4(),
            filename=storage_filename,
            original_filename=filename,
            mime_type=content_type,
            size_bytes=len(file_data),
            storage_key=storage_filename,
            bucket=settings.minio_bucket,
            url=url,
            thumbnail_url=thumbnail_url,
            uploaded_by_id=uploaded_by_id,
            scan_status="clean",  # TODO: Integrate virus scanning
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        db.add(file_record)
        await db.commit()
        await db.refresh(file_record)

        # Publish file.uploaded event
        await kafka_producer.publish_event(
            topic=settings.kafka_topic,
            key=str(file_record.id),
            event_type="file.uploaded",
            data={
                "file_id": str(file_record.id),
                "filename": filename,
                "content_type": content_type,
                "size": len(file_data),
                "is_image": is_image,
                "channel_id": str(channel_id) if channel_id else None,
                "message_id": str(message_id) if message_id else None,
                "uploaded_by": str(uploaded_by_id),
                "url": url,
                "created_at": file_record.created_at.isoformat(),
            },
        )

        logger.info(f"Uploaded file: {filename} ({file_record.id})")
        return file_record

    async def get_file(self, db: AsyncSession, file_id: UUID) -> Optional[File]:
        """Get file by ID.

        Args:
            db: Database session
            file_id: File ID

        Returns:
            File model or None
        """
        stmt = select(File).where(File.id == file_id, File.deleted_at.is_(None))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_file_with_uploader(self, db: AsyncSession, file_id: UUID) -> Optional[Tuple[File, User]]:
        """Get file with uploader information.

        Args:
            db: Database session
            file_id: File ID

        Returns:
            Tuple of (File, User) or None
        """
        stmt = (
            select(File, User)
            .join(User, File.uploaded_by_id == User.id)
            .where(File.id == file_id, File.deleted_at.is_(None))
        )
        result = await db.execute(stmt)
        row = result.first()
        return row if row else None

    async def list_files(
        self,
        db: AsyncSession,
        channel_id: Optional[UUID] = None,
        message_id: Optional[UUID] = None,
        file_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Tuple[File, User]], int]:
        """List files with filters.

        Args:
            db: Database session
            channel_id: Filter by channel
            message_id: Filter by message
            file_type: Filter by type ("image", "video", "document")
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (files_with_uploaders, total_count)
        """
        # Build base query
        query = select(File, User).join(User, File.uploaded_by_id == User.id).where(File.deleted_at.is_(None))

        # Apply filters
        if channel_id:
            # TODO: Join with message_attachments table when implemented
            pass

        if message_id:
            # TODO: Join with message_attachments table when implemented
            pass

        if file_type:
            if file_type == "image":
                query = query.where(File.mime_type.startswith("image/"))
            elif file_type == "video":
                query = query.where(File.mime_type.startswith("video/"))
            elif file_type == "document":
                query = query.where(File.mime_type.startswith("application/"))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        result = await db.execute(count_query)
        total_count = result.scalar() or 0

        # Apply pagination
        query = query.order_by(desc(File.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        # Execute query
        result = await db.execute(query)
        files = result.all()

        return files, total_count

    async def delete_file(
        self,
        db: AsyncSession,
        file_id: UUID,
        deleted_by_id: UUID,
    ) -> bool:
        """Soft delete file.

        Args:
            db: Database session
            file_id: File ID
            deleted_by_id: User deleting the file

        Returns:
            True if deleted successfully
        """
        file_record = await self.get_file(db, file_id)
        if not file_record:
            return False

        # Soft delete in database
        file_record.deleted_at = datetime.now(timezone.utc)
        await db.commit()

        # Delete from MinIO (async - don't wait)
        try:
            minio_service.delete_file(file_record.storage_key)
            if file_record.thumbnail_url:
                thumb_key = f"thumb_{file_record.storage_key}"
                minio_service.delete_file(thumb_key, bucket=settings.minio_thumbnails_bucket)
        except Exception as e:
            logger.error(f"Error deleting file from MinIO: {e}")

        # Publish file.deleted event
        await kafka_producer.publish_event(
            topic=settings.kafka_topic,
            key=str(file_id),
            event_type="file.deleted",
            data={
                "file_id": str(file_id),
                "filename": file_record.original_filename,
                "deleted_by": str(deleted_by_id),
                "deleted_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info(f"Deleted file: {file_id}")
        return True


# Global file manager instance
file_manager = FileManager()
