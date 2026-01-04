"""JSON Schema for Paheko exporter configuration."""

SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Paheko Exporter Configuration",
    "description": "Configuration for exporting data to Paheko accounting software",
    "type": "object",
    "properties": {
        "api_url": {
            "type": "string",
            "title": "API URL",
            "description": "Paheko instance API URL (e.g., https://myassociation.paheko.cloud/api/)",
            "format": "uri",
        },
        "api_user": {
            "type": "string",
            "title": "API User",
            "description": "API username for Basic Auth",
        },
        "vault_api_key_path": {
            "type": "string",
            "title": "Vault API Key Path",
            "description": "Path to API key in Vault (auto-filled)",
            "readOnly": True,
        },
        "default_year_id": {
            "type": "integer",
            "title": "Default Year ID",
            "description": "Default accounting year ID (leave empty for auto-match by date)",
        },
        "verify_ssl": {
            "type": "boolean",
            "title": "Verify SSL",
            "description": "Verify SSL certificates for API requests",
            "default": True,
        },
        "duplicate_check": {
            "type": "boolean",
            "title": "Check Duplicates",
            "description": "Check for existing transactions before creating",
            "default": True,
        },
        "duplicate_field": {
            "type": "string",
            "title": "Duplicate Check Field",
            "description": "Record field to use for duplicate detection",
            "default": "invoice_id",
        },
    },
    "required": ["api_url"],
}
