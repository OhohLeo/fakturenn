"""Data models for raw source data.

These models represent the raw data fetched from sources before
being transformed by parsers into Records.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawAttachment:
    """Represents an email attachment."""

    id: str
    filename: str
    mime_type: str
    size: int
    content: bytes | None = None  # Lazy-loaded


@dataclass
class RawEmail:
    """Represents a raw email from Gmail.

    Contains both metadata (for listing) and full content (when fetched).
    """

    id: str
    thread_id: str
    subject: str
    from_address: str
    to_address: str
    date: datetime
    snippet: str = ""

    # Full content (populated when get_item is called)
    body_html: str | None = None
    body_text: str | None = None
    attachments: list[RawAttachment] = field(default_factory=list)

    # Gmail-specific metadata
    label_ids: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class RawRow:
    """Represents a raw row from an Excel spreadsheet."""

    row_number: int
    data: dict[str, str | int | float | datetime | None]

    # Original values before type conversion
    raw_values: list[str | int | float | None] = field(default_factory=list)

    # Source file info
    sheet_name: str = ""
    file_path: str = ""


@dataclass
class RawInvoice:
    """Represents a raw invoice from Free/FreeMobile (Phase 2).

    Placeholder for future Selenium-based scraping.
    """

    id: str
    date: datetime
    amount: float
    status: str
    download_url: str
    pdf_content: bytes | None = None
