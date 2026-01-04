"""Base class for all source implementations.

Sources are the connection layer - they handle:
- Authentication with external services
- Fetching raw data (emails, rows, invoices)
- Downloading attachments

Sources do NOT transform data - that's the parser's job.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")  # Type of raw item (RawEmail, RawRow, etc.)


class SourceError(Exception):
    """Base exception for source operations."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


class ConnectionError(SourceError):
    """Raised when connection to source fails."""

    pass


class AuthenticationError(SourceError):
    """Raised when authentication fails."""

    pass


class FetchError(SourceError):
    """Raised when fetching data fails."""

    pass


class BaseSource(ABC, Generic[T]):
    """Abstract base class for all source implementations.

    Each source type (Gmail, XLS, Free, etc.) implements this interface
    to provide a consistent way to:
    1. Connect/authenticate
    2. List available items
    3. Get item details
    4. Download attachments (if applicable)
    """

    def __init__(self, source_id: str, config: dict[str, Any]):
        """Initialize source with configuration.

        Args:
            source_id: UUID of the Source record (used for Vault paths)
            config: Source configuration from database
        """
        self.source_id = source_id
        self.config = config
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if source is connected."""
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the source.

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
    async def list_items(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[T]:
        """List available items from the source.

        Args:
            filters: Optional filters to apply (source-specific)
            limit: Maximum number of items to return

        Returns:
            List of raw items (metadata only, not full content)

        Raises:
            FetchError: If fetching fails
        """
        pass

    @abstractmethod
    async def get_item(self, item_id: str) -> T:
        """Get full details of a specific item.

        Args:
            item_id: Unique identifier for the item

        Returns:
            Raw item with full content

        Raises:
            FetchError: If item not found or fetch fails
        """
        pass

    async def download_attachment(
        self,
        item_id: str,
        attachment_id: str,
    ) -> bytes:
        """Download an attachment from an item.

        Default implementation raises NotImplementedError.
        Override in sources that support attachments.

        Args:
            item_id: Item containing the attachment
            attachment_id: Attachment to download

        Returns:
            Attachment content as bytes

        Raises:
            NotImplementedError: If source doesn't support attachments
            FetchError: If download fails
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support attachments"
        )

    async def __aenter__(self) -> "BaseSource[T]":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()
