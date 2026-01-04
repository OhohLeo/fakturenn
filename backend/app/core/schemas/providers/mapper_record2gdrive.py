"""JSON Schema for Record2GDrive mapper configuration."""

SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Record2GDrive Mapper Configuration",
    "description": "Configuration for uploading record files to Google Drive",
    "type": "object",
    "properties": {
        "filename_template": {
            "type": "string",
            "title": "Filename Template",
            "description": "Template for uploaded filename (e.g., '{source_type}_{date}_{invoice_id}.pdf')",
            "default": "{date}_{invoice_id}.pdf",
        },
        "folder_structure": {
            "type": "string",
            "title": "Folder Structure",
            "description": "Subfolder pattern (e.g., '{year}/{month}')",
            "default": "{year}/{month}",
        },
        "skip_if_no_file": {
            "type": "boolean",
            "title": "Skip If No File",
            "description": "Skip records that don't have an attached file",
            "default": True,
        },
        "file_field": {
            "type": "string",
            "title": "File Field",
            "description": "Record field containing the file path",
            "default": "file_path",
        },
        "metadata_fields": {
            "type": "array",
            "title": "Metadata Fields",
            "description": "Record fields to include as file metadata/description",
            "items": {"type": "string"},
            "default": ["invoice_id", "date", "amount_text"],
        },
        "content_type": {
            "type": "string",
            "title": "Content Type",
            "description": "MIME type for uploaded files",
            "default": "application/pdf",
        },
    },
    "required": [],
}
