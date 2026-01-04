"""XLS2Record parser implementation.

Transforms Excel spreadsheet rows into Records using column mapping.
"""

from datetime import date, datetime
from typing import Any

from app.parsers.base import BaseParser, ExtractionError, ParsedRecord
from app.sources.models import RawRow
from app.sources.xls import XLSSource


class XLS2RecordParser(BaseParser[RawRow]):
    """Parser that extracts invoice data from Excel rows.

    Rules schema (from Parser.rules JSONB):
        column_mapping: Map column names/letters to record fields
            A: "invoice_id"
            B: "date"
            C: "amount_text"
            D: "description"

        date_column: Column containing the record date (default: "B")
        date_format: strptime format for parsing dates (empty = auto-detect)

        filters: Row filters
            date_after: Only include rows with date after this value
            date_before: Only include rows with date before this value
            column_equals: {column: value} filters
            column_contains: {column: substring} filters

        skip_empty_rows: Skip rows where all values are empty (default: true)
        trim_whitespace: Trim whitespace from values (default: true)

    Example rules:
        {
            "column_mapping": {
                "A": "invoice_id",
                "B": "date",
                "C": "amount_text",
                "D": "description"
            },
            "date_column": "B",
            "date_format": "%d/%m/%Y",
            "filters": {
                "date_after": "2024-01-01"
            }
        }
    """

    source: XLSSource

    async def parse(self, limit: int = 100) -> list[ParsedRecord]:
        """Parse Excel rows into records.

        Args:
            limit: Maximum number of rows to process

        Returns:
            List of ParsedRecord objects
        """
        # Get filters from rules
        filters = self.rules.get("filters", {})

        # List rows from source
        rows = await self.source.list_items(filters=filters, limit=limit)

        records = []
        for row in rows:
            try:
                record = await self.parse_item(row)
                if record:
                    records.append(record)
            except ExtractionError:
                # Log and skip rows that fail extraction
                continue

        return records

    async def parse_item(self, item: RawRow) -> ParsedRecord | None:
        """Parse a single Excel row into a record.

        Args:
            item: Row data from spreadsheet

        Returns:
            ParsedRecord if extraction succeeds, None if should be skipped
        """
        # Get column mapping
        column_mapping = self.rules.get("column_mapping", {})
        if not column_mapping:
            raise ExtractionError("No column_mapping defined in rules")

        # Build record data using mapping
        data: dict[str, Any] = {}
        trim_whitespace = self.rules.get("trim_whitespace", True)

        for col_id, field_name in column_mapping.items():
            value = item.data.get(col_id)

            # Trim whitespace if configured
            if trim_whitespace and isinstance(value, str):
                value = value.strip()

            if value is not None and value != "":
                data[field_name] = value

        # Check for empty record
        if self.rules.get("skip_empty_rows", True):
            if all(v is None or v == "" for v in data.values()):
                return None

        # Extract date
        date_column = self.rules.get("date_column", "B")
        date_value = item.data.get(date_column)
        record_date = self._parse_date(date_value)

        if not record_date:
            raise ExtractionError(
                f"Failed to parse date from row {item.row_number}",
                {"date_value": date_value, "date_column": date_column},
            )

        # Add row metadata
        data["row_number"] = item.row_number
        data["sheet_name"] = item.sheet_name

        record = ParsedRecord(
            record_date=record_date,
            data=data,
            source_item_id=str(item.row_number),
            extraction_metadata={
                "extraction_method": "column_mapping",
                "file_path": item.file_path,
                "sheet_name": item.sheet_name,
            },
        )

        self._validate_record(record)
        return record

    def _parse_date(self, value: Any) -> date | None:
        """Parse date from various formats."""
        if value is None:
            return None

        # Already a date/datetime
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()

        # Parse string
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None

            # Try configured format first
            date_format = self.rules.get("date_format", "")
            if date_format:
                try:
                    return datetime.strptime(value, date_format).date()
                except ValueError:
                    pass

            # Try common formats
            formats = [
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%d-%m-%Y",
                "%Y/%m/%d",
                "%d.%m.%Y",
                "%m/%d/%Y",
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue

        # Try to handle Excel numeric dates
        if isinstance(value, int | float):
            try:
                # Excel stores dates as days since 1899-12-30
                from datetime import timedelta

                excel_epoch = datetime(1899, 12, 30)
                return (excel_epoch + timedelta(days=int(value))).date()
            except (ValueError, OverflowError):
                pass

        return None
