"""JSON Schema for XLS source configuration."""

SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "XLS Source Configuration",
    "description": "Configuration for reading data from Excel spreadsheets",
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "title": "File Path",
            "description": "Path to the Excel file (or MinIO path)",
        },
        "sheet_name": {
            "type": "string",
            "title": "Sheet Name",
            "description": "Name of the sheet to read (defaults to first sheet)",
        },
        "sheet_index": {
            "type": "integer",
            "title": "Sheet Index",
            "description": "Index of the sheet to read (0-based, used if sheet_name not provided)",
            "minimum": 0,
            "default": 0,
        },
        "header_row": {
            "type": "integer",
            "title": "Header Row",
            "description": "Row number containing headers (0-based)",
            "minimum": 0,
            "default": 0,
        },
        "skip_rows": {
            "type": "integer",
            "title": "Skip Rows",
            "description": "Number of rows to skip after header",
            "minimum": 0,
            "default": 0,
        },
        "use_columns": {
            "type": "array",
            "title": "Columns to Use",
            "description": "List of column names or indices to read (empty = all columns)",
            "items": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "integer"},
                ],
            },
            "default": [],
        },
        "date_columns": {
            "type": "array",
            "title": "Date Columns",
            "description": "Column names that contain dates (for proper parsing)",
            "items": {"type": "string"},
            "default": [],
        },
    },
    "required": [],
}
