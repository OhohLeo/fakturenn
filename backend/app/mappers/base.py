"""Base class for all mapper implementations.

Mappers are the transformation layer for exports - they handle:
- Transforming Record data into exporter-specific format
- Applying transformation rules (templates, field mapping)
- Calling the exporter to create entries

Mappers use an Exporter to send the transformed data.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.exports.base import BaseExporter
from app.models import Record


class MapperError(Exception):
    """Base exception for mapper operations."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


class TransformationError(MapperError):
    """Raised when data transformation fails."""

    pass


class BaseMapper(ABC):
    """Abstract base class for all mapper implementations.

    Each mapper type (Record2Paheko, Record2GDrive, etc.) implements this
    interface to transform Records and send them to an Exporter.

    Usage:
        async with exporter:
            mapper = Record2PahekoMapper(exporter, rules)
            success = await mapper.transform_and_export(record)
    """

    def __init__(self, exporter: BaseExporter, rules: dict[str, Any]):
        """Initialize mapper with exporter and rules.

        Args:
            exporter: Connected exporter to send data to
            rules: Mapper rules from Mapper.transformation_logic JSONB field
        """
        self.exporter = exporter
        self.rules = rules

    @abstractmethod
    async def transform_and_export(self, record: Record) -> bool:
        """Transform a Record and export it.

        This method should:
        1. Apply transformation rules to convert Record to export format
        2. Check for duplicates (optional)
        3. Call exporter.create_entry() to send the data

        Args:
            record: Record to transform and export

        Returns:
            True if export succeeded, False if skipped (e.g., duplicate)

        Raises:
            MapperError: If transformation or export fails
        """
        pass

    def _render_template(self, template: str, context: dict[str, Any]) -> str:
        """Render a template string with context values.

        Supports simple {field} placeholders.

        Args:
            template: Template string with {field} placeholders
            context: Dict of values to substitute

        Returns:
            Rendered string
        """
        result = template
        for key, value in context.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value) if value is not None else "")
        return result

    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float.

        Handles common European formats:
        - "1 234,56" -> 1234.56
        - "1.234,56" -> 1234.56
        - "1234.56" -> 1234.56

        Args:
            amount_str: Amount as string

        Returns:
            Amount as float
        """
        if not amount_str:
            return 0.0

        # Get parsing config from rules
        parsing = self.rules.get("amount_parsing", {})
        decimal_sep = parsing.get("decimal_separator", ",")
        thousands_sep = parsing.get("thousands_separator", " ")
        currency_symbol = parsing.get("currency_symbol", "€")

        # Clean the string
        cleaned = str(amount_str).strip()

        # Remove currency symbol
        if currency_symbol:
            cleaned = cleaned.replace(currency_symbol, "").strip()

        # Remove thousands separator
        if thousands_sep:
            cleaned = cleaned.replace(thousands_sep, "")

        # Replace decimal separator with .
        if decimal_sep and decimal_sep != ".":
            cleaned = cleaned.replace(decimal_sep, ".")

        try:
            return float(cleaned)
        except ValueError:
            return 0.0
