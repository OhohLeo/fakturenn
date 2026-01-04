"""Mail2Record parser implementation.

Transforms Gmail emails into Records using regex extraction rules.
"""

import re
from datetime import date, datetime
from typing import Any

from app.parsers.base import BaseParser, ExtractionError, ParsedRecord
from app.sources.gmail import GmailSource
from app.sources.models import RawEmail


class Mail2RecordParser(BaseParser[RawEmail]):
    """Parser that extracts invoice data from emails using regex.

    Rules schema (from Parser.rules JSONB):
        filters: Additional email filters
            from: Sender email filter
            subject_contains: Subject filter
            after_date: Date filter (YYYY-MM-DD)

        extraction_regex: Regex patterns for extraction
            email_html: Regex for HTML body (use named groups)
            email_text: Fallback regex for plain text body

        field_mapping: Map regex groups to record fields
            invoice_id: "invoice_id"
            date: "date"
            amount_text: "amount_text"

        date_format: strptime format for parsing dates (default: "%d/%m/%Y")

        download_attachments: Whether to download PDF attachments (default: true)
        attachment_filter: Regex to filter attachments by filename (default: "\\.pdf$")

    Example rules:
        {
            "filters": {
                "from": "factures@provider.com",
                "subject_contains": "Facture"
            },
            "extraction_regex": {
                "email_html": "<TD>(?P<invoice_id>\\d+)</TD>.*?<TD>(?P<date>\\d{2}/\\d{2}/\\d{4})</TD>.*?<TD>(?P<amount_text>[\\d,]+)</TD>",
                "email_text": "Facture n°(?P<invoice_id>\\d+).*Date: (?P<date>\\d{2}/\\d{2}/\\d{4}).*Total: (?P<amount_text>[\\d,]+)"
            },
            "date_format": "%d/%m/%Y",
            "download_attachments": true
        }
    """

    source: GmailSource

    async def parse(self, limit: int = 100) -> list[ParsedRecord]:
        """Parse emails into records.

        Args:
            limit: Maximum number of emails to process

        Returns:
            List of ParsedRecord objects
        """
        # Get filters from rules
        filters = self.rules.get("filters", {})

        # List emails from source
        emails = await self.source.list_items(filters=filters, limit=limit)

        records = []
        for email in emails:
            try:
                # Get full email content
                full_email = await self.source.get_item(email.id)
                record = await self.parse_item(full_email)
                if record:
                    records.append(record)
            except ExtractionError:
                # Log and skip emails that fail extraction
                continue

        return records

    async def parse_item(self, item: RawEmail) -> ParsedRecord | None:
        """Parse a single email into a record.

        Args:
            item: Full email with body content

        Returns:
            ParsedRecord if extraction succeeds, None if should be skipped
        """
        # Extract data using regex
        extracted = self._extract_with_regex(item)
        if not extracted:
            return None

        # Parse date
        record_date = self._parse_date(extracted.get("date", ""))
        if not record_date:
            raise ExtractionError(
                f"Failed to parse date from email {item.id}",
                {"extracted_date": extracted.get("date")},
            )

        # Build record data
        field_mapping = self.rules.get("field_mapping", {
            "invoice_id": "invoice_id",
            "date": "date",
            "amount_text": "amount_text",
        })

        data: dict[str, Any] = {}
        for regex_group, record_field in field_mapping.items():
            if regex_group in extracted:
                data[record_field] = extracted[regex_group]

        # Add email metadata
        data["email_subject"] = item.subject
        data["email_from"] = item.from_address
        data["email_id"] = item.id

        # Download attachment if configured
        file_content = None
        file_name = None
        if self.rules.get("download_attachments", True) and item.attachments:
            attachment = self._find_matching_attachment(item)
            if attachment:
                file_content = await self.source.download_attachment(
                    item.id, attachment.id
                )
                file_name = attachment.filename

        record = ParsedRecord(
            record_date=record_date,
            data=data,
            file_content=file_content,
            file_name=file_name,
            source_item_id=item.id,
            extraction_metadata={
                "extraction_method": "regex",
                "matched_pattern": "email_html" if item.body_html else "email_text",
                "raw_extracted": extracted,
            },
        )

        self._validate_record(record)
        return record

    def _extract_with_regex(self, email: RawEmail) -> dict[str, str]:
        """Extract data from email using regex patterns.

        Tries HTML body first, then falls back to plain text.
        """
        extraction_regex = self.rules.get("extraction_regex", {})

        # Try HTML body first
        if email.body_html and "email_html" in extraction_regex:
            pattern = extraction_regex["email_html"]
            match = re.search(pattern, email.body_html, re.DOTALL | re.IGNORECASE)
            if match:
                return match.groupdict()

        # Fall back to plain text
        if email.body_text and "email_text" in extraction_regex:
            pattern = extraction_regex["email_text"]
            match = re.search(pattern, email.body_text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.groupdict()

        return {}

    def _parse_date(self, date_str: str) -> date | None:
        """Parse date string using configured format."""
        if not date_str:
            return None

        date_format = self.rules.get("date_format", "%d/%m/%Y")

        # Try configured format first
        try:
            return datetime.strptime(date_str.strip(), date_format).date()
        except ValueError:
            pass

        # Try common formats as fallback
        fallback_formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d.%m.%Y",
        ]
        for fmt in fallback_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue

        return None

    def _find_matching_attachment(self, email: RawEmail) -> Any:
        """Find first attachment matching the filter pattern."""
        attachment_filter = self.rules.get("attachment_filter", r"\.pdf$")
        pattern = re.compile(attachment_filter, re.IGNORECASE)

        for attachment in email.attachments:
            if pattern.search(attachment.filename):
                return attachment

        return None
