"""JSON Schema for Google Drive exporter configuration."""

SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Google Drive Exporter Configuration",
    "description": "Configuration for uploading files to Google Drive",
    "type": "object",
    "properties": {
        "root_folder_id": {
            "type": "string",
            "title": "Root Folder ID",
            "description": "Google Drive folder ID where files will be uploaded",
        },
        "folder_structure": {
            "type": "string",
            "title": "Folder Structure",
            "description": "Subfolder pattern using record fields (e.g., '{year}/{month}')",
            "default": "{year}/{month}",
        },
        "create_folders": {
            "type": "boolean",
            "title": "Create Folders",
            "description": "Automatically create folders if they don't exist",
            "default": True,
        },
        "vault_credentials_path": {
            "type": "string",
            "title": "Vault Credentials Path",
            "description": "Path to OAuth credentials in Vault (auto-filled)",
            "readOnly": True,
        },
        "duplicate_check": {
            "type": "boolean",
            "title": "Check Duplicates",
            "description": "Check for existing files before uploading",
            "default": True,
        },
        "duplicate_action": {
            "type": "string",
            "title": "Duplicate Action",
            "description": "Action when duplicate file is found",
            "enum": ["skip", "replace", "rename"],
            "default": "skip",
        },
    },
    "required": ["root_folder_id"],
}
