"""Parser implementations for transforming raw data into Records.

Parsers apply rules to raw source data (emails, rows) and extract
structured Record data with invoice information.
"""

from app.parsers.base import BaseParser, ParserError, ParsedRecord

__all__ = [
    "BaseParser",
    "ParserError",
    "ParsedRecord",
]
