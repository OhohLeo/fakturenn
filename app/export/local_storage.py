"""LocalStorage export handler for organizing PDFs in filesystem."""

import logging
import shutil
from pathlib import Path
from typing import Any, Dict

from app.export.base import ExportHandler, ExportResult
from app.core.path_template import render_path_template, validate_path_template

logger = logging.getLogger(__name__)


class LocalStorageExportHandler(ExportHandler):
    """Handler for exporting invoices to local filesystem."""

    async def export(
        self,
        invoice_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> ExportResult:
        """Export invoice PDF to local storage.

        Args:
            invoice_data: Must contain 'file_path' (source PDF)
            context: Context with template variables

        Returns:
            ExportResult with destination path as reference
        """
        try:
            if not self._validate_invoice_data(invoice_data):
                return ExportResult(
                    status="failed",
                    error_message="Missing required invoice data fields",
                )

            if not self._validate_context(context):
                return ExportResult(
                    status="failed",
                    error_message="Missing required context fields",
                )

            # Validate template
            path_template = self.config.get("path_template", "{year}/{month}/{source}_{invoice_id}.pdf")
            is_valid, error = validate_path_template(path_template)
            if not is_valid:
                return ExportResult(status="failed", error_message=error)

            # Get base path
            base_path = Path(self.config.get("base_path", "factures"))
            if not base_path.is_absolute():
                base_path = Path.cwd() / base_path

            # Render destination path
            context_for_template = {
                **context,
                "source": invoice_data.get("source", "unknown"),
                "filename": Path(invoice_data["file_path"]).name,
            }
            relative_path = render_path_template(path_template, context_for_template)
            destination_path = base_path / relative_path

            # Create directories if needed
            if self.config.get("create_directories", True):
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {destination_path.parent}")

            # Copy file
            source_path = Path(invoice_data["file_path"])
            if not source_path.exists():
                return ExportResult(
                    status="failed",
                    error_message=f"Source file not found: {source_path}",
                )

            shutil.copy2(source_path, destination_path)
            logger.info(f"Exported PDF to: {destination_path}")

            return ExportResult(
                status="success",
                external_reference=str(destination_path),
            )

        except Exception as e:
            logger.error(f"LocalStorage export failed: {e}")
            return ExportResult(
                status="failed",
                error_message=str(e),
            )
