"""MinIO service for file storage operations."""

import logging
from datetime import timedelta
from io import BytesIO
from typing import Optional, Tuple

from minio import Minio
from minio.error import S3Error

from config import settings

logger = logging.getLogger(__name__)


class MinIOService:
    """Service for interacting with MinIO object storage."""

    def __init__(self):
        """Initialize MinIO client."""
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket
        self.thumbnails_bucket = settings.minio_thumbnails_bucket

    async def initialize_buckets(self):
        """Create buckets if they don't exist."""
        try:
            # Create main files bucket
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created MinIO bucket: {self.bucket}")
            else:
                logger.info(f"MinIO bucket already exists: {self.bucket}")

            # Create thumbnails bucket
            if not self.client.bucket_exists(self.thumbnails_bucket):
                self.client.make_bucket(self.thumbnails_bucket)
                logger.info(f"Created MinIO bucket: {self.thumbnails_bucket}")
            else:
                logger.info(f"MinIO bucket already exists: {self.thumbnails_bucket}")

        except S3Error as e:
            logger.error(f"Error creating MinIO buckets: {e}")
            raise

    def check_connection(self) -> bool:
        """Check if MinIO is accessible."""
        try:
            self.client.bucket_exists(self.bucket)
            return True
        except Exception as e:
            logger.error(f"MinIO connection check failed: {e}")
            return False

    def upload_file(
        self,
        file_data: bytes,
        object_name: str,
        content_type: str,
        bucket: Optional[str] = None,
    ) -> str:
        """Upload file to MinIO.

        Args:
            file_data: File content as bytes
            object_name: Name/path of object in bucket
            content_type: MIME type of file
            bucket: Bucket name (defaults to main bucket)

        Returns:
            URL to access the file
        """
        target_bucket = bucket or self.bucket

        try:
            # Upload file
            self.client.put_object(
                bucket_name=target_bucket,
                object_name=object_name,
                data=BytesIO(file_data),
                length=len(file_data),
                content_type=content_type,
            )

            # Generate URL
            url = f"{settings.minio_public_endpoint}/{target_bucket}/{object_name}"
            logger.info(f"Uploaded file to MinIO: {url}")
            return url

        except S3Error as e:
            logger.error(f"Error uploading file to MinIO: {e}")
            raise

    def download_file(self, object_name: str, bucket: Optional[str] = None) -> Tuple[bytes, str]:
        """Download file from MinIO.

        Args:
            object_name: Name/path of object in bucket
            bucket: Bucket name (defaults to main bucket)

        Returns:
            Tuple of (file_data, content_type)
        """
        target_bucket = bucket or self.bucket

        try:
            response = self.client.get_object(target_bucket, object_name)
            data = response.read()
            content_type = response.headers.get("Content-Type", "application/octet-stream")
            response.close()
            response.release_conn()

            return data, content_type

        except S3Error as e:
            logger.error(f"Error downloading file from MinIO: {e}")
            raise

    def delete_file(self, object_name: str, bucket: Optional[str] = None) -> bool:
        """Delete file from MinIO.

        Args:
            object_name: Name/path of object in bucket
            bucket: Bucket name (defaults to main bucket)

        Returns:
            True if deletion successful
        """
        target_bucket = bucket or self.bucket

        try:
            self.client.remove_object(target_bucket, object_name)
            logger.info(f"Deleted file from MinIO: {target_bucket}/{object_name}")
            return True

        except S3Error as e:
            logger.error(f"Error deleting file from MinIO: {e}")
            return False

    def generate_presigned_url(
        self,
        object_name: str,
        expiry_minutes: int = 60,
        bucket: Optional[str] = None,
    ) -> str:
        """Generate presigned URL for temporary access.

        Args:
            object_name: Name/path of object in bucket
            expiry_minutes: URL expiry time in minutes
            bucket: Bucket name (defaults to main bucket)

        Returns:
            Presigned URL
        """
        target_bucket = bucket or self.bucket

        try:
            url = self.client.presigned_get_object(
                bucket_name=target_bucket,
                object_name=object_name,
                expires=timedelta(minutes=expiry_minutes),
            )
            return url

        except S3Error as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise

    def get_file_info(self, object_name: str, bucket: Optional[str] = None) -> dict:
        """Get file metadata from MinIO.

        Args:
            object_name: Name/path of object in bucket
            bucket: Bucket name (defaults to main bucket)

        Returns:
            Dictionary with file metadata
        """
        target_bucket = bucket or self.bucket

        try:
            stat = self.client.stat_object(target_bucket, object_name)
            return {
                "size": stat.size,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "etag": stat.etag,
            }

        except S3Error as e:
            logger.error(f"Error getting file info from MinIO: {e}")
            raise


# Global MinIO service instance
minio_service = MinIOService()
