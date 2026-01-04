"""Record2GDrive mapper implementation.

Transforms Records into Google Drive file uploads.
"""

from typing import Any

from app.core.storage import get_storage, StorageError
from app.exports.base import DuplicateError
from app.exports.gdrive import GDriveExporter
from app.mappers.base import BaseMapper, TransformationError
from app.models import Record


class Record2GDriveMapper(BaseMapper):
    """Mapper that uploads Record files to Google Drive.

    Rules schema (from Mapper.transformation_logic JSONB):
        filename_template: Template for uploaded filename
            e.g., "{date}_{invoice_id}.pdf"

        folder_structure: Subfolder pattern
            e.g., "{year}/{month}"

        skip_if_no_file: Skip records without attached files
            default: true

        file_field: Record field containing the file path
            e.g., "file_path"

        metadata_fields: Record fields to include in file description
            e.g., ["invoice_id", "date", "amount_text"]

        content_type: MIME type for uploaded files
            default: "application/pdf"

    Example rules:
        {
            "filename_template": "{source_type}_{date}_{invoice_id}.pdf",
            "folder_structure": "{year}/{month}",
            "skip_if_no_file": true,
            "file_field": "file_path",
            "metadata_fields": ["invoice_id", "date", "amount_text"],
            "content_type": "application/pdf"
        }
    """

    exporter: GDriveExporter

    async def transform_and_export(self, record: Record) -> bool:
        """Transform Record and upload file to Google Drive.

        Args:
            record: Record to transform and export

        Returns:
            True if export succeeded, False if skipped

        Raises:
            TransformationError: If transformation fails
        """
        # Check for file
        skip_if_no_file = self.rules.get("skip_if_no_file", True)
        if not record.file_path:
            if skip_if_no_file:
                return False  # Skip records without files
            raise TransformationError(
                "Record has no file and skip_if_no_file is false",
                {"record_id": str(record.id)},
            )

        # Build context for templates
        context = self._build_context(record)

        # Build filename
        filename_template = self.rules.get(
            "filename_template",
            "{date}_{invoice_id}.pdf"
        )
        filename = self._render_template(filename_template, context)

        # Get or create target folder
        folder_structure = self.rules.get("folder_structure", "{year}/{month}")
        folder_path = self._render_template(folder_structure, context)

        try:
            folder_id = await self.exporter.get_or_create_folder(folder_path)
        except Exception as e:
            raise TransformationError(
                f"Failed to create folder structure: {e}",
                {"folder_path": folder_path},
            ) from e

        # Load file content from MinIO
        try:
            storage = get_storage()
            file_content = storage.download_file(record.file_path)
        except StorageError as e:
            raise TransformationError(
                f"Failed to load file from storage: {e}",
                {"file_path": record.file_path},
            ) from e

        # Build description from metadata fields
        description = self._build_description(record)

        # Prepare upload data
        content_type = self.rules.get("content_type", "application/pdf")
        upload_data = {
            "filename": filename,
            "content": file_content,
            "content_type": content_type,
            "folder_id": folder_id,
            "description": description,
        }

        # Upload file
        try:
            await self.exporter.create_entry(upload_data)
            return True
        except DuplicateError:
            return False

    def _build_context(self, record: Record) -> dict[str, Any]:
        """Build template context from record."""
        context: dict[str, Any] = {}

        # Add record data fields
        if record.data:
            context.update(record.data)

        # Add date-based fields
        if record.date:
            context["date"] = record.date.isoformat()
            context["year"] = str(record.date.year)
            context["month"] = f"{record.date.month:02d}"
            context["day"] = f"{record.date.day:02d}"

        # Add source type if available
        context["source_type"] = context.get("source_type", "invoice")

        return context

    def _build_description(self, record: Record) -> str:
        """Build file description from metadata fields."""
        metadata_fields = self.rules.get(
            "metadata_fields",
            ["invoice_id", "date", "amount_text"]
        )

        parts = []
        for field in metadata_fields:
            value = None
            if field == "date" and record.date:
                value = record.date.isoformat()
            elif record.data:
                value = record.data.get(field)

            if value is not None:
                parts.append(f"{field}: {value}")

        return "\n".join(parts)
