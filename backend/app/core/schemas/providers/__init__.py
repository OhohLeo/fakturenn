"""Provider-specific JSON Schema definitions for SDUI forms."""

from app.core.schemas.providers import (
    exporter_gdrive,
    exporter_paheko,
    mapper_record2gdrive,
    mapper_record2paheko,
    parser_mail2record,
    parser_xls2record,
    source_gmail,
    source_xls,
)

__all__ = [
    "source_gmail",
    "source_xls",
    "parser_mail2record",
    "parser_xls2record",
    "exporter_paheko",
    "exporter_gdrive",
    "mapper_record2paheko",
    "mapper_record2gdrive",
]
