"""XLS source implementation.

Provides connectivity to Excel spreadsheets for reading invoice data.
Supports both local files and files stored in MinIO.
"""

import io
from datetime import datetime
from typing import Any

import openpyxl
from openpyxl.utils import get_column_letter

from app.core.storage import get_storage, StorageError
from app.sources.base import BaseSource, ConnectionError, FetchError
from app.sources.models import RawRow


class XLSSource(BaseSource[RawRow]):
    """Excel spreadsheet source for reading tabular data.

    Configuration (from Source.config):
        file_path: Path to Excel file (local or MinIO path)
        sheet_name: Name of sheet to read (optional, defaults to first)
        sheet_index: Index of sheet to read (0-based, used if sheet_name not set)
        header_row: Row number containing headers (0-based, default: 0)
        skip_rows: Number of rows to skip after header (default: 0)
        use_columns: List of column names/indices to read (empty = all)
        date_columns: Column names that contain dates

    Note: This source reads files into memory. For very large files,
    consider streaming or chunking approaches.
    """

    def __init__(self, source_id: str, config: dict[str, Any]):
        super().__init__(source_id, config)
        self._workbook = None
        self._sheet = None
        self._headers: list[str] = []
        self._data_start_row: int = 0

    async def connect(self) -> None:
        """Load the Excel file into memory.

        Loads from local filesystem or MinIO based on file_path prefix.
        """
        file_path = self.config.get("file_path", "")
        if not file_path:
            raise ConnectionError("No file_path configured")

        try:
            # Determine if file is in MinIO or local
            if file_path.startswith("minio://") or "/" in file_path and not file_path.startswith("/"):
                # Load from MinIO
                storage = get_storage()
                # Remove minio:// prefix if present
                minio_path = file_path.replace("minio://", "")
                content = storage.download_file(minio_path)
                self._workbook = openpyxl.load_workbook(
                    io.BytesIO(content),
                    data_only=True,  # Return values, not formulas
                )
            else:
                # Load from local filesystem
                self._workbook = openpyxl.load_workbook(
                    file_path,
                    data_only=True,
                )

            # Select sheet
            sheet_name = self.config.get("sheet_name")
            if sheet_name:
                if sheet_name not in self._workbook.sheetnames:
                    raise ConnectionError(
                        f"Sheet '{sheet_name}' not found. Available: {self._workbook.sheetnames}"
                    )
                self._sheet = self._workbook[sheet_name]
            else:
                sheet_index = self.config.get("sheet_index", 0)
                if sheet_index >= len(self._workbook.sheetnames):
                    raise ConnectionError(
                        f"Sheet index {sheet_index} out of range. "
                        f"File has {len(self._workbook.sheetnames)} sheets."
                    )
                self._sheet = self._workbook.worksheets[sheet_index]

            # Read headers
            header_row = self.config.get("header_row", 0) + 1  # openpyxl is 1-indexed
            self._headers = []
            for cell in self._sheet[header_row]:
                if cell.value is not None:
                    self._headers.append(str(cell.value))
                else:
                    # Use column letter for empty headers
                    self._headers.append(get_column_letter(cell.column))

            # Calculate data start row
            skip_rows = self.config.get("skip_rows", 0)
            self._data_start_row = header_row + 1 + skip_rows

            self._connected = True

        except StorageError as e:
            raise ConnectionError(f"Failed to load file from MinIO: {e}") from e
        except FileNotFoundError as e:
            raise ConnectionError(f"File not found: {file_path}") from e
        except Exception as e:
            raise ConnectionError(f"Failed to load Excel file: {e}") from e

    async def disconnect(self) -> None:
        """Close workbook and release resources."""
        if self._workbook:
            self._workbook.close()
        self._workbook = None
        self._sheet = None
        self._headers = []
        self._connected = False

    async def list_items(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[RawRow]:
        """List rows from the spreadsheet.

        Args:
            filters: Optional filters (date_after, date_before, column_equals)
            limit: Maximum rows to return

        Returns:
            List of RawRow objects
        """
        if not self._connected or not self._sheet:
            raise ConnectionError("Not connected to spreadsheet")

        rows = []
        use_columns = self.config.get("use_columns", [])
        date_columns = set(self.config.get("date_columns", []))

        for row_idx, row in enumerate(
            self._sheet.iter_rows(min_row=self._data_start_row),
            start=self._data_start_row,
        ):
            if len(rows) >= limit:
                break

            # Build row data dict
            data: dict[str, Any] = {}
            raw_values: list[Any] = []

            for col_idx, cell in enumerate(row):
                raw_values.append(cell.value)

                # Skip columns not in use_columns (if specified)
                if use_columns:
                    col_id = self._headers[col_idx] if col_idx < len(self._headers) else get_column_letter(col_idx + 1)
                    if col_id not in use_columns and col_idx not in use_columns:
                        continue

                # Get header name for this column
                header = self._headers[col_idx] if col_idx < len(self._headers) else get_column_letter(col_idx + 1)

                # Parse value
                value = cell.value
                if header in date_columns and value is not None:
                    if isinstance(value, datetime):
                        data[header] = value
                    elif isinstance(value, str):
                        # Try to parse date string
                        data[header] = self._parse_date(value)
                    else:
                        data[header] = value
                else:
                    data[header] = value

            # Skip empty rows
            if self.config.get("skip_empty_rows", True):
                if all(v is None or v == "" for v in data.values()):
                    continue

            # Apply filters
            if filters and not self._matches_filters(data, filters):
                continue

            raw_row = RawRow(
                row_number=row_idx,
                data=data,
                raw_values=raw_values,
                sheet_name=self._sheet.title,
                file_path=self.config.get("file_path", ""),
            )
            rows.append(raw_row)

        return rows

    async def get_item(self, item_id: str) -> RawRow:
        """Get a specific row by row number.

        Args:
            item_id: Row number as string

        Returns:
            RawRow for the specified row
        """
        if not self._connected or not self._sheet:
            raise ConnectionError("Not connected to spreadsheet")

        try:
            row_number = int(item_id)
        except ValueError:
            raise FetchError(f"Invalid row number: {item_id}")

        if row_number < self._data_start_row:
            raise FetchError(f"Row {row_number} is before data start row")

        try:
            row = list(self._sheet.iter_rows(min_row=row_number, max_row=row_number))[0]
        except IndexError:
            raise FetchError(f"Row {row_number} not found")

        date_columns = set(self.config.get("date_columns", []))
        data: dict[str, Any] = {}
        raw_values: list[Any] = []

        for col_idx, cell in enumerate(row):
            raw_values.append(cell.value)
            header = self._headers[col_idx] if col_idx < len(self._headers) else get_column_letter(col_idx + 1)

            value = cell.value
            if header in date_columns and value is not None:
                if isinstance(value, datetime):
                    data[header] = value
                elif isinstance(value, str):
                    data[header] = self._parse_date(value)
                else:
                    data[header] = value
            else:
                data[header] = value

        return RawRow(
            row_number=row_number,
            data=data,
            raw_values=raw_values,
            sheet_name=self._sheet.title,
            file_path=self.config.get("file_path", ""),
        )

    def _parse_date(self, value: str) -> datetime | str:
        """Try to parse a date string."""
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d.%m.%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return value  # Return original if parsing fails

    def _matches_filters(self, data: dict[str, Any], filters: dict[str, Any]) -> bool:
        """Check if row matches the specified filters."""
        # Date after filter
        if "date_after" in filters:
            date_col = self.config.get("date_column", "date")
            row_date = data.get(date_col)
            if row_date:
                filter_date = filters["date_after"]
                if isinstance(filter_date, str):
                    filter_date = self._parse_date(filter_date)
                if isinstance(row_date, datetime) and isinstance(filter_date, datetime):
                    if row_date < filter_date:
                        return False

        # Date before filter
        if "date_before" in filters:
            date_col = self.config.get("date_column", "date")
            row_date = data.get(date_col)
            if row_date:
                filter_date = filters["date_before"]
                if isinstance(filter_date, str):
                    filter_date = self._parse_date(filter_date)
                if isinstance(row_date, datetime) and isinstance(filter_date, datetime):
                    if row_date > filter_date:
                        return False

        # Column equals filter
        if "column_equals" in filters:
            for col, expected in filters["column_equals"].items():
                if str(data.get(col, "")) != str(expected):
                    return False

        # Column contains filter
        if "column_contains" in filters:
            for col, substring in filters["column_contains"].items():
                if substring.lower() not in str(data.get(col, "")).lower():
                    return False

        return True
