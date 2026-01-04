"""MinIO/S3 storage client for file storage.

Stores invoice PDFs and other files in MinIO (S3-compatible object storage).
"""

import hashlib
import io
from datetime import date, timedelta
from uuid import UUID

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class StorageError(Exception):
    """Raised when storage operations fail."""

    pass


class StorageClient:
    """MinIO/S3 storage client for file operations."""

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        secure: bool | None = None,
    ):
        """Initialize MinIO client.

        Args:
            endpoint: MinIO endpoint (host:port)
            access_key: Access key for authentication
            secret_key: Secret key for authentication
            bucket: Bucket name for file storage
            secure: Use HTTPS (default: False for dev)
        """
        self.endpoint = endpoint or settings.MINIO_ENDPOINT
        self.bucket = bucket or settings.MINIO_BUCKET
        self._secure = secure if secure is not None else settings.MINIO_SECURE

        self.client = Minio(
            self.endpoint,
            access_key=access_key or settings.MINIO_ACCESS_KEY,
            secret_key=secret_key or settings.MINIO_SECRET_KEY,
            secure=self._secure,
        )

    def ensure_bucket(self) -> None:
        """Ensure the bucket exists, create if not."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            raise StorageError(f"Failed to ensure bucket exists: {e}") from e

    def upload_file(
        self,
        workflow_id: UUID,
        record_date: date,
        source_type: str,
        invoice_id: str,
        content: bytes,
        content_type: str = "application/pdf",
    ) -> tuple[str, str]:
        """Upload file to MinIO.

        Storage structure:
            {bucket}/{workflow_id}/{year}/{month}/{source_type}_{date}_{invoice_id}.pdf

        Args:
            workflow_id: Workflow UUID
            record_date: Date of the record
            source_type: Type of source (gmail, xls, etc.)
            invoice_id: Invoice identifier
            content: File content as bytes
            content_type: MIME type of the file

        Returns:
            Tuple of (file_path, file_hash)

        Raises:
            StorageError: If upload fails
        """
        file_hash = hashlib.sha256(content).hexdigest()[:16]

        # Build path: workflow_id/year/month/source_date_invoice.pdf
        path = (
            f"{workflow_id}/{record_date.year}/{record_date.month:02d}/"
            f"{source_type}_{record_date.isoformat()}_{invoice_id}.pdf"
        )

        try:
            self.client.put_object(
                self.bucket,
                path,
                io.BytesIO(content),
                len(content),
                content_type=content_type,
            )
            return path, file_hash
        except S3Error as e:
            raise StorageError(f"Failed to upload file: {e}") from e

    def download_file(self, path: str) -> bytes:
        """Download file from MinIO.

        Args:
            path: Object path in bucket

        Returns:
            File content as bytes

        Raises:
            StorageError: If download fails
        """
        try:
            response = self.client.get_object(self.bucket, path)
            return response.read()
        except S3Error as e:
            raise StorageError(f"Failed to download file: {e}") from e
        finally:
            if "response" in locals():
                response.close()
                response.release_conn()

    def file_exists(self, path: str) -> bool:
        """Check if file exists in storage.

        Args:
            path: Object path in bucket

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.stat_object(self.bucket, path)
            return True
        except S3Error:
            return False

    def delete_file(self, path: str) -> None:
        """Delete file from storage.

        Args:
            path: Object path in bucket

        Raises:
            StorageError: If deletion fails
        """
        try:
            self.client.remove_object(self.bucket, path)
        except S3Error as e:
            raise StorageError(f"Failed to delete file: {e}") from e

    def get_presigned_url(
        self,
        path: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """Get presigned URL for direct browser download.

        Args:
            path: Object path in bucket
            expires: URL expiration time

        Returns:
            Presigned URL string

        Raises:
            StorageError: If URL generation fails
        """
        try:
            return self.client.presigned_get_object(
                self.bucket,
                path,
                expires=expires,
            )
        except S3Error as e:
            raise StorageError(f"Failed to generate presigned URL: {e}") from e

    def list_files(self, prefix: str = "") -> list[str]:
        """List files in storage with optional prefix filter.

        Args:
            prefix: Path prefix to filter (e.g., "workflow_id/2024/")

        Returns:
            List of object paths
        """
        try:
            objects = self.client.list_objects(self.bucket, prefix=prefix)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            raise StorageError(f"Failed to list files: {e}") from e


# Global storage client instance
_storage: StorageClient | None = None


def get_storage() -> StorageClient:
    """Get or create global storage client singleton."""
    global _storage
    if _storage is None:
        _storage = StorageClient()
        _storage.ensure_bucket()
    return _storage
