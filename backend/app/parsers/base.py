"""Base class for all parser implementations.

Parsers are the transformation layer - they handle:
- Applying rules to raw source data
- Extracting structured information (invoice ID, date, amount)
- Creating ParsedRecord objects ready to become Records

Parsers use a Source to fetch raw data and apply rules to transform it.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Generic, TypeVar

from app.sources.base import BaseSource

T = TypeVar("T")  # Type of raw item from source


class ParserError(Exception):
    """Base exception for parser operations."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


class ExtractionError(ParserError):
    """Raised when data extraction fails."""

    pass


class ValidationError(ParserError):
    """Raised when parsed data fails validation."""

    pass


@dataclass
class ParsedRecord:
    """Represents a successfully parsed record.

    This is the intermediate format between raw source data and a Record entity.
    Contains all extracted information ready to be persisted.
    """

    # Required fields
    record_date: date
    data: dict[str, Any]

    # Optional file attachment
    file_content: bytes | None = None
    file_name: str | None = None

    # Source tracking
    source_item_id: str = ""  # ID of the source item (email ID, row number)
    extraction_metadata: dict[str, Any] = field(default_factory=dict)

    # Computed fields (will be set when creating Record)
    unique_key: str | None = None
    file_hash: str | None = None


class BaseParser(ABC, Generic[T]):
    """Abstract base class for all parser implementations.

    Each parser type (Mail2Record, XLS2Record, etc.) implements this interface
    to transform raw source data into ParsedRecords.

    Usage:
        async with source:
            parser = Mail2RecordParser(source, rules)
            records = await parser.parse()
    """

    def __init__(self, source: BaseSource[T], rules: dict[str, Any]):
        """Initialize parser with source and rules.

        Args:
            source: Connected source to fetch raw data from
            rules: Parser rules from Parser.rules JSONB field
        """
        self.source = source
        self.rules = rules

    @abstractmethod
    async def parse(self, limit: int = 100) -> list[ParsedRecord]:
        """Parse raw source data into records.

        This method should:
        1. Fetch items from the source (using source.list_items)
        2. For each item, apply extraction rules
        3. Create ParsedRecord objects

        Args:
            limit: Maximum number of items to process

        Returns:
            List of ParsedRecord objects

        Raises:
            ParserError: If parsing fails
        """
        pass

    @abstractmethod
    async def parse_item(self, item: T) -> ParsedRecord | None:
        """Parse a single raw item into a record.

        Args:
            item: Raw item from source

        Returns:
            ParsedRecord if successful, None if item should be skipped

        Raises:
            ExtractionError: If extraction fails
        """
        pass

    def _validate_record(self, record: ParsedRecord) -> None:
        """Validate a parsed record before returning.

        Override in subclasses for custom validation.

        Args:
            record: Parsed record to validate

        Raises:
            ValidationError: If validation fails
        """
        if not record.record_date:
            raise ValidationError("Record date is required")
        if not record.data:
            raise ValidationError("Record data cannot be empty")
