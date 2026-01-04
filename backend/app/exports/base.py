"""Base class for all exporter implementations.

Exporters are the connection layer for export destinations - they handle:
- Authentication with external services
- Creating entries (transactions, files)
- Checking for duplicates

Exporters do NOT transform data - that's the mapper's job.
"""

from abc import ABC, abstractmethod
from typing import Any


class ExporterError(Exception):
    """Base exception for exporter operations."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


class ConnectionError(ExporterError):
    """Raised when connection to export destination fails."""

    pass


class AuthenticationError(ExporterError):
    """Raised when authentication fails."""

    pass


class ExportError(ExporterError):
    """Raised when export operation fails."""

    pass


class DuplicateError(ExporterError):
    """Raised when entry already exists."""

    pass


class BaseExporter(ABC):
    """Abstract base class for all exporter implementations.

    Each exporter type (Paheko, GDrive, etc.) implements this interface
    to provide a consistent way to:
    1. Connect/authenticate
    2. Create entries
    3. Check for duplicates
    """

    def __init__(self, exporter_id: str, config: dict[str, Any]):
        """Initialize exporter with configuration.

        Args:
            exporter_id: UUID of the Exporter record (used for Vault paths)
            config: Exporter configuration from database
        """
        self.exporter_id = exporter_id
        self.config = config
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if exporter is connected."""
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the export destination.

        This should:
        - Load credentials from Vault
        - Authenticate with the service
        - Set up any necessary clients

        Raises:
            AuthenticationError: If authentication fails
            ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection and clean up resources."""
        pass

    @abstractmethod
    async def create_entry(self, data: dict[str, Any]) -> str:
        """Create an entry in the export destination.

        Args:
            data: Entry data (format depends on exporter type)

        Returns:
            ID of the created entry

        Raises:
            ExportError: If creation fails
            DuplicateError: If entry already exists (when duplicate_check enabled)
        """
        pass

    @abstractmethod
    async def check_duplicate(self, identifier: str) -> bool:
        """Check if an entry already exists.

        Args:
            identifier: Unique identifier to check

        Returns:
            True if entry exists, False otherwise

        Raises:
            ExportError: If check fails
        """
        pass

    async def __aenter__(self) -> "BaseExporter":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()
