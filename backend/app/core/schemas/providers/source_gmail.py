"""JSON Schema for Gmail source configuration."""

SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Gmail Source Configuration",
    "description": "Configuration for fetching emails from Gmail",
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "title": "Gmail Search Query",
            "description": "Gmail search query to filter emails (e.g., 'from:billing@example.com subject:Invoice')",
            "default": "",
        },
        "sender_from": {
            "type": "string",
            "title": "Sender Email",
            "description": "Filter emails from this sender address",
            "format": "email",
        },
        "subject_contains": {
            "type": "string",
            "title": "Subject Contains",
            "description": "Filter emails with subject containing this text",
        },
        "max_results": {
            "type": "integer",
            "title": "Max Results",
            "description": "Maximum number of emails to fetch per sync",
            "default": 100,
            "minimum": 1,
            "maximum": 500,
        },
        "after_date": {
            "type": "string",
            "title": "After Date",
            "description": "Only fetch emails after this date (YYYY-MM-DD)",
            "format": "date",
        },
        "label_ids": {
            "type": "array",
            "title": "Gmail Labels",
            "description": "Gmail label IDs to filter (e.g., ['INBOX', 'Label_123'])",
            "items": {"type": "string"},
            "default": ["INBOX"],
        },
        "vault_credentials_path": {
            "type": "string",
            "title": "Vault Credentials Path",
            "description": "Path to OAuth credentials in Vault (auto-filled)",
            "readOnly": True,
        },
    },
    "required": [],
}
