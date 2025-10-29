"""Base export handler interface."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    """Result of an export operation."""

    status: str  # "success", "failed", "duplicate_skipped"
    external_reference: Optional[str] = None  # Paheko transaction ID, file path, Drive file ID
    error_message: Optional[str] = None


class ExportHandler(ABC):
    """Base class for export handlers."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize handler with configuration.

        Args:
            config: Export-specific configuration
        """
        self.config = config

    @abstractmethod
    async def export(
        self,
        invoice_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> ExportResult:
        """Execute export operation.

        Args:
            invoice_data: Invoice data (file_path, amount_eur, invoice_id, date, source)
            context: Context variables (invoice_id, date, amount_eur, month, year, quarter)

        Returns:
            ExportResult with status and reference
        """
        pass

    def _validate_invoice_data(self, invoice_data: Dict[str, Any]) -> bool:
        """Validate required invoice data fields.

        Args:
            invoice_data: Invoice data dictionary

        Returns:
            True if valid
        """
        required_fields = ["file_path", "invoice_id", "date", "amount_eur"]
        return all(field in invoice_data for field in required_fields)

    def _validate_context(self, context: Dict[str, Any]) -> bool:
        """Validate required context fields.

        Args:
            context: Context dictionary

        Returns:
            True if valid
        """
        required_fields = ["invoice_id", "date", "amount_eur"]
        return all(field in context for field in required_fields)


def get_export_handler(
    export_type: str,
    config: Dict[str, Any],
    **kwargs: Any,
) -> ExportHandler:
    """Factory function to get appropriate export handler.

    Args:
        export_type: Type of export (Paheko, LocalStorage, GoogleDrive)
        config: Export configuration
        **kwargs: Additional arguments for handler (vault_client, user_id, etc.)

    Returns:
        Initialized export handler

    Raises:
        ValueError: If export type is unknown
    """
    if export_type == "Paheko":
        from app.export.paheko_handler import PahekoExportHandler

        return PahekoExportHandler(config, **kwargs)
    elif export_type == "LocalStorage":
        from app.export.local_storage import LocalStorageExportHandler

        return LocalStorageExportHandler(config)
    elif export_type == "GoogleDrive":
        from app.export.google_drive import GoogleDriveExportHandler

        return GoogleDriveExportHandler(config, **kwargs)
    else:
        raise ValueError(f"Unknown export type: {export_type}")
