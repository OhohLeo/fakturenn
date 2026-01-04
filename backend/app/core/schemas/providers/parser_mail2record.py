"""JSON Schema for Mail2Record parser configuration."""

SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Mail2Record Parser Configuration",
    "description": "Configuration for parsing emails into records using regex extraction",
    "type": "object",
    "properties": {
        "filters": {
            "type": "object",
            "title": "Email Filters",
            "description": "Additional filters applied to fetched emails",
            "properties": {
                "from": {
                    "type": "string",
                    "title": "From Address",
                    "description": "Filter by sender email address",
                },
                "subject_contains": {
                    "type": "string",
                    "title": "Subject Contains",
                    "description": "Filter emails with subject containing this text",
                },
                "after_date": {
                    "type": "string",
                    "title": "After Date",
                    "description": "Only process emails after this date",
                    "format": "date",
                },
            },
        },
        "extraction_regex": {
            "type": "object",
            "title": "Extraction Regex Patterns",
            "description": "Named regex patterns for extracting data from email content",
            "properties": {
                "email_html": {
                    "type": "string",
                    "title": "HTML Body Regex",
                    "description": "Regex pattern for HTML body extraction (use named groups like (?P<invoice_id>...))",
                },
                "email_text": {
                    "type": "string",
                    "title": "Text Body Regex",
                    "description": "Fallback regex for plain text body extraction",
                },
            },
        },
        "field_mapping": {
            "type": "object",
            "title": "Field Mapping",
            "description": "Map regex group names to record fields",
            "additionalProperties": {"type": "string"},
            "default": {
                "invoice_id": "invoice_id",
                "date": "date",
                "amount_text": "amount_text",
            },
        },
        "date_format": {
            "type": "string",
            "title": "Date Format",
            "description": "Expected date format in emails (strptime format)",
            "default": "%d/%m/%Y",
        },
        "download_attachments": {
            "type": "boolean",
            "title": "Download Attachments",
            "description": "Download PDF attachments from emails",
            "default": True,
        },
        "attachment_filter": {
            "type": "string",
            "title": "Attachment Filter",
            "description": "Regex pattern to filter attachment filenames (e.g., '\\.pdf$')",
            "default": "\\.pdf$",
        },
    },
    "required": [],
}
