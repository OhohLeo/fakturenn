import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from pathlib import Path
import re

from app.sources.free import FreeInvoiceDownloader
from app.sources.free_mobile import FreeMobileInvoiceDownloader
from app.sources.invoice import Invoice
from app.core.date_utils import parse_date_label_to_date
from app.sources.gmail_manager import GmailManager

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

logger = logging.getLogger(__name__)


class SourceRunner:
    def __init__(
        self,
        output_dir: str,
        gmail_manager: Optional[GmailManager] = None,
    ) -> None:
        self.output_dir = output_dir
        self.gmail = gmail_manager
        self._marker_converter = None
        self._marker_models = None

    def _filter_invoices_from_date(self, invoices: List[Invoice], from_date: date) -> List[Invoice]:
        filtered: List[Invoice] = []
        for inv in invoices:
            inv_dt = parse_date_label_to_date(inv.date or "")
            if inv_dt and inv_dt >= from_date:
                filtered.append(inv)
        return filtered

    def _convert_named_groups(self, pattern: str) -> str:
        # Convert JS-style (?<name>...) to Python (?P<name>...)
        return re.sub(r"\(\?<([a-zA-Z_][a-zA-Z0-9_]*)>", r"(?P<\1>", pattern)

    def _parse_amount_eur(self, amount_text: Optional[str]) -> Optional[float]:
        if not amount_text:
            return None
        txt = amount_text.strip()
        txt = txt.replace("€", "").replace(" ", "")
        # Convert French decimal comma to dot
        txt = txt.replace(",", ".")
        try:
            return float(txt)
        except Exception as e:
            logger.error(f"Failed to parse amount '{amount_text}': {e}")
            return None

    def _normalize_date_str(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        s = raw.strip()
        # dd/mm/yyyy -> yyyy-mm-dd
        m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", s)
        if m:
            dd, mm, yyyy = m.groups()
            return f"{yyyy}-{mm}-{dd}"
        # Try to parse whatever else using helper
        d = parse_date_label_to_date(s)
        if d:
            return d.strftime("%Y-%m-%d")
        return s

    def _get_marker_converter(self):
        """Lazy initialization of Marker converter."""
        if self._marker_converter is None:
            try:
                self._marker_models = create_model_dict()
                self._marker_converter = PdfConverter(
                    artifact_dict=self._marker_models,
                )
                logger.info("Marker PDF converter initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Marker converter: {e}")
                return None

        return self._marker_converter

    def _convert_pdf_to_markdown(self, pdf_path: str) -> Optional[str]:
        """Convert a PDF file to markdown using Marker."""
        converter = self._get_marker_converter()
        if not converter:
            return None

        try:
            pdf_file_path = Path(pdf_path)
            if not pdf_file_path.exists():
                logger.error(f"PDF file not found: {pdf_path}")
                return None

            # Marker expects a string path, not a Path object
            rendered = converter(str(pdf_file_path))
            markdown_text, _, _ = text_from_rendered(rendered)
            logger.info(f"Successfully converted PDF to markdown: {pdf_path}")
            return markdown_text
        except Exception as e:
            logger.error(f"Failed to convert PDF to markdown: {e}")
            return None

    def _run_free_invoice(self, from_date: date) -> List[Invoice]:
        """Execute FreeInvoice source."""
        downloader = FreeInvoiceDownloader(
            login=os.getenv("FREE_LOGIN"),
            password=os.getenv("FREE_PASSWORD"),
            output_dir=self.output_dir,
            headless=os.getenv("HEADLESS_MODE", "true").lower() == "true",
        )
        try:
            from_date_str = from_date.strftime("%Y-%m-%d")
            try:
                _, _ = downloader.download_invoices_from(from_date_str)
            except Exception as e:
                logger.warning(f"Téléchargement via 'download_invoices_from' a échoué: {e}")

            invoices: List[Invoice] = []
            current_year = datetime.now().year
            for y in range(from_date.year, current_year + 1):
                try:
                    invs = downloader.get_invoices_by_year(y)
                    invoices.extend(invs)
                except Exception:
                    continue
            invoices = self._filter_invoices_from_date(invoices, from_date)

            downloaded_invoices: List[Invoice] = []
            for inv in invoices:
                filename = inv.suggested_filename(prefix="Free")
                filepath = os.path.join(self.output_dir, filename)
                if os.path.exists(filepath):
                    downloaded_invoices.append(inv)

            return downloaded_invoices
        finally:
            downloader.close()

    def _run_free_mobile_invoice(self, from_date: date) -> List[Invoice]:
        """Execute FreeMobileInvoice source."""
        downloader = FreeMobileInvoiceDownloader(
            login=os.getenv("FREE_MOBILE_LOGIN"),
            password=os.getenv("FREE_MOBILE_PASSWORD"),
            gmail_credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH", "gmail.json"),
            gmail_token_path=os.getenv("GMAIL_TOKEN_PATH", "gmail.json"),
            output_dir=self.output_dir,
        )
        try:
            from_date_str = from_date.strftime("%Y-%m-%d")
            invoices = downloader.get_invoices_list(from_date=from_date_str)
            filtered = self._filter_invoices_from_date(invoices, from_date)
            downloaded_invoices: List[Invoice] = []
            for inv in filtered:
                if downloader.download_invoice(inv):
                    downloaded_invoices.append(inv)
            return downloaded_invoices
        finally:
            downloader.close()

    def _normalize_patterns(self, pattern_value: Any) -> List[re.Pattern]:
        """Convert a single pattern or list of patterns to a list of compiled regex patterns."""
        if isinstance(pattern_value, str):
            # Single pattern as string
            return [re.compile(self._convert_named_groups(pattern_value), re.DOTALL)]
        elif isinstance(pattern_value, list):
            # Multiple patterns as list
            patterns = []
            for p in pattern_value:
                if isinstance(p, str):
                    patterns.append(re.compile(self._convert_named_groups(p), re.DOTALL))
            return patterns
        return []

    def _run_gmail_source(
        self,
        from_date: date,
        email_sender_from: Optional[str],
        email_subject_contains: Optional[str],
        max_results: int,
        extraction_params: Dict[str, Any],
    ) -> List[Invoice]:
        """Execute Gmail source with flexible extraction patterns."""
        if not self.gmail:
            logger.error("GmailManager non initialisé")
            return []

        if not extraction_params:
            logger.error("Extraction params non fournis")
            return []

        # Build Gmail search query
        query_parts: List[str] = []
        if email_sender_from:
            query_parts.append(f"from:{email_sender_from}")
        if email_subject_contains:
            query_parts.append(f"subject:'{email_subject_contains}'")
        query_parts.append(f"after:{from_date.strftime('%Y/%m/%d')}")
        query_parts.append("has:attachment")
        query = " ".join(query_parts)

        emails = self.gmail.search_emails(query, max_results=max_results) or []
        if not emails:
            logger.info("Aucun email correspondant")
            return []

        # Determine extraction source and patterns
        source = None
        patterns: List[re.Pattern] = []
        use_attachment_markdown = False

        # Check for markdown_text pattern(s)
        if extraction_params.get("markdown_text"):
            use_attachment_markdown = True
            source = "markdown_text"
            patterns = self._normalize_patterns(extraction_params.get("markdown_text"))
            logger.info(f"Regex 'markdown_text' valide: {len(patterns)} pattern(s)")
        else:
            # Fall back to email body patterns
            for source_expected, source_actual in {
                "email_html": "body_html",
                "email_text": "body_text",
            }.items():
                if extraction_params.get(source_expected):
                    source = source_actual
                    patterns = self._normalize_patterns(extraction_params.get(source_expected))
                    logger.info(f"Regex '{source_expected}' valide: {len(patterns)} pattern(s)")
                    break

        if not patterns:
            logger.error("Aucun pattern valide trouvé")
            return []

        # Download attachments first
        saved_attachment_paths = self.gmail.download_attachments_from_emails(emails, self.output_dir)
        logger.info(f"Nombre de pièces jointes téléchargées: {len(saved_attachment_paths)}")

        # Extract invoice data
        extracted_invoices: List[Invoice] = []

        if use_attachment_markdown:
            # Extract from PDF attachments converted to markdown
            extracted_invoices = self._extract_from_attachment_markdown(emails, saved_attachment_paths, patterns)
        else:
            # Extract from email body
            extracted_invoices = self._extract_from_email_body(emails, source, patterns)

        # Filter by date
        filtered_invoices = self._filter_invoices_from_date(extracted_invoices, from_date)

        return filtered_invoices

    def _extract_from_email_body(self, emails: List[Dict], source: str, patterns: List[re.Pattern]) -> List[Invoice]:
        """Extract invoice data from email body (HTML or text) using multiple patterns."""
        extracted_invoices: List[Invoice] = []

        for email in emails:
            body = email.get(source) or ""
            logger.info(f"Body: {body}")
            date_email = email.get("date") or ""
            logger.info(f"Date email: {date_email}")

            # Collect all extracted data from all patterns
            extracted_data: Dict[str, Any] = {}

            try:
                # Apply each pattern and merge results
                for pattern_idx, pattern in enumerate(patterns):
                    for m in pattern.finditer(body):
                        logger.info(f"Match from pattern {pattern_idx + 1} '{str(pattern)}': {m.groupdict()}")
                        # Merge captured groups, later patterns can override earlier ones
                        for key, value in m.groupdict().items():
                            if value is not None:
                                extracted_data[key] = value

                # If we have any extracted data, create an invoice
                if extracted_data:
                    inv_id = extracted_data.get("invoice_id") or None
                    date_raw = extracted_data.get("date") or date_email
                    amount_text = extracted_data.get("amount_text") or None
                    date_norm = self._normalize_date_str(date_raw) or ""
                    amount_eur = self._parse_amount_eur(amount_text)

                    extracted_invoices.append(
                        Invoice(
                            date=date_norm,
                            invoice_id=inv_id,
                            amount_text=amount_text,
                            amount_eur=amount_eur,
                            download_url=None,
                            view_url=None,
                            source="Gmail",
                        )
                    )
            except Exception as e:
                logger.warning(f"Erreur lors de l'extraction sur l'email {email.get('id')}: {e}")

        return extracted_invoices

    def _extract_from_attachment_markdown(
        self, emails: List[Dict], saved_attachment_paths: List[str], patterns: List[re.Pattern]
    ) -> List[Invoice]:
        """Extract invoice data from PDF attachments converted to markdown using multiple patterns."""
        extracted_invoices: List[Invoice] = []

        # Filter to only process PDF attachments
        pdf_paths = [path for path in saved_attachment_paths if path.lower().endswith(".pdf")]
        logger.info(f"Found {len(pdf_paths)} PDF attachments to process")

        for email in emails:
            date_email = email.get("date") or ""
            logger.info(f"Processing email: {email.get('id')} dated {date_email}")

            # Process all PDF attachments
            for attachment_path in pdf_paths:
                # Convert PDF to markdown
                markdown_text = self._convert_pdf_to_markdown(attachment_path)
                if not markdown_text:
                    logger.warning(f"Could not convert PDF to markdown: {attachment_path}")
                    continue

                logger.info(f"Markdown text: {markdown_text}")

                # Collect all extracted data from all patterns
                extracted_data: Dict[str, Any] = {}

                # Apply regex patterns to markdown text
                try:
                    # Apply each pattern and merge results
                    for pattern_idx, pattern in enumerate(patterns):
                        for m in pattern.finditer(markdown_text):
                            logger.info(f"Match from pattern {pattern_idx + 1} {str(pattern)}: {m.groupdict()}")
                            # Merge captured groups, later patterns can override earlier ones
                            for key, value in m.groupdict().items():
                                if value is not None:
                                    extracted_data[key] = value

                    # If we have any extracted data, create an invoice
                    if extracted_data:
                        inv_id = extracted_data.get("invoice_id") or None
                        date_raw = extracted_data.get("date") or date_email
                        amount_text = extracted_data.get("amount_text") or None
                        date_norm = self._normalize_date_str(date_raw) or ""
                        amount_eur = self._parse_amount_eur(amount_text)

                        extracted_invoices.append(
                            Invoice(
                                date=date_norm,
                                invoice_id=inv_id,
                                amount_text=amount_text,
                                amount_eur=amount_eur,
                                download_url=None,
                                view_url=attachment_path,
                                source="Gmail",
                            )
                        )
                except Exception as e:
                    logger.warning(f"Erreur lors de l'extraction du PDF {attachment_path}: {e}")

        return extracted_invoices

    def run(
        self,
        source_name: str,
        from_date: date,
        email_sender_from: Optional[str] = None,
        email_subject_contains: Optional[str] = None,
        max_results: int = 30,
        extraction_params: Optional[Dict[str, Any]] = None,
    ) -> List[Invoice]:
        """
        Main entry point to run a specific source.

        Args:
            source_name: Name of the source ("FreeInvoice", "FreeMobileInvoice", "Gmail")
            from_date: Start date for invoice retrieval
            email_sender_from: Email sender filter (for Gmail source)
            email_subject_contains: Email subject filter (for Gmail source)
            max_results: Maximum number of emails to process (for Gmail source)
            extraction_params: Extraction configuration (for Gmail source)
                - email_html: Regex pattern(s) for HTML body (string or list of strings)
                - email_text: Regex pattern(s) for text body (string or list of strings)
                - markdown_text: Regex pattern(s) for PDF attachment converted to markdown (string or list of strings)

                Each pattern can contain named groups: invoice_id, date, amount_text
                When using multiple patterns, extracted data is merged (later patterns override earlier ones)

        Returns:
            List of Invoice objects
        """
        if source_name == "FreeInvoice":
            return self._run_free_invoice(from_date)

        elif source_name == "FreeMobileInvoice":
            return self._run_free_mobile_invoice(from_date)

        elif source_name == "Gmail":
            return self._run_gmail_source(
                from_date=from_date,
                email_sender_from=email_sender_from,
                email_subject_contains=email_subject_contains,
                max_results=max_results,
                extraction_params=extraction_params or {},
            )

        else:
            logger.error(f"Source inconnue: {source_name}")
            return []
