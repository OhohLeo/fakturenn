"""Source implementations for data extraction.

Sources provide connectivity to external data providers:
- Gmail: Email fetching via Gmail API
- XLS: Excel spreadsheet reading
- Free/FreeMobile: Web scraping (Phase 2 - deferred)
"""

from app.sources.base import BaseSource, SourceError
from app.sources.models import RawAttachment, RawEmail, RawRow

__all__ = [
    "BaseSource",
    "SourceError",
    "RawEmail",
    "RawRow",
    "RawAttachment",
]
