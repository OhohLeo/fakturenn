from dataclasses import dataclass
from typing import Optional


@dataclass
class Invoice:
    """Generic invoice representation used by downloaders.

    - date: human-readable date label (e.g., "Janvier 2025" or "2025-01").
    - invoice_id: provider-specific identifier when available.
    - amount_text: raw textual amount as found on the page (e.g., "19,99€").
    - amount_eur: parsed numeric amount when available.
    - download_url: absolute URL to download the PDF.
    - view_url: absolute URL to view the invoice page (optional).
    - source: logical source name (e.g., "Free", "FreeMobile").
    """

    date: str
    invoice_id: Optional[str] = None
    amount_text: Optional[str] = None
    amount_eur: Optional[float] = None
    download_url: Optional[str] = None
    view_url: Optional[str] = None
    source: Optional[str] = None

    def suggested_filename(self, prefix: str) -> str:
        date_str = (self.date or "").replace(" ", "_")
        id_part = self.invoice_id or "unknown"
        return f"{prefix}_{date_str}_{id_part}.pdf"
