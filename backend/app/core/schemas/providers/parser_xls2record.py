"""JSON Schema for XLS2Record parser configuration."""

SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "XLS2Record Parser Configuration",
    "description": "Configuration for parsing Excel rows into records",
    "type": "object",
    "properties": {
        "column_mapping": {
            "type": "object",
            "title": "Column Mapping",
            "description": "Map Excel column names/letters to record fields",
            "additionalProperties": {"type": "string"},
            "default": {
                "A": "invoice_id",
                "B": "date",
                "C": "amount_text",
                "D": "description",
            },
        },
        "date_column": {
            "type": "string",
            "title": "Date Column",
            "description": "Column containing the record date",
            "default": "B",
        },
        "date_format": {
            "type": "string",
            "title": "Date Format",
            "description": "Expected date format (strptime format, empty = auto-detect)",
            "default": "",
        },
        "filters": {
            "type": "object",
            "title": "Row Filters",
            "description": "Filters to apply on rows",
            "properties": {
                "date_after": {
                    "type": "string",
                    "title": "Date After",
                    "description": "Only include rows with date after this value",
                    "format": "date",
                },
                "date_before": {
                    "type": "string",
                    "title": "Date Before",
                    "description": "Only include rows with date before this value",
                    "format": "date",
                },
                "column_equals": {
                    "type": "object",
                    "title": "Column Equals",
                    "description": "Filter rows where column equals value",
                    "additionalProperties": {"type": "string"},
                },
                "column_contains": {
                    "type": "object",
                    "title": "Column Contains",
                    "description": "Filter rows where column contains value",
                    "additionalProperties": {"type": "string"},
                },
            },
        },
        "skip_empty_rows": {
            "type": "boolean",
            "title": "Skip Empty Rows",
            "description": "Skip rows where all mapped columns are empty",
            "default": True,
        },
        "trim_whitespace": {
            "type": "boolean",
            "title": "Trim Whitespace",
            "description": "Trim leading/trailing whitespace from values",
            "default": True,
        },
    },
    "required": [],
}
