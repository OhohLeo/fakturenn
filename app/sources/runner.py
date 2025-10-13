import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import re

from app.sources.free import FreeInvoiceDownloader
from app.sources.free_mobile import FreeMobileInvoiceDownloader
from app.sources.invoice import Invoice
from app.core.date_utils import parse_date_label_to_date
from app.sources.gmail_manager import GmailManager


logger = logging.getLogger(__name__)


class SourceRunner:
    def __init__(
        self,
        output_dir: str,
        gmail_manager: Optional[GmailManager] = None,
    ) -> None:
        self.output_dir = output_dir
        self.gmail = gmail_manager

    def _filter_invoices_from_date(
        self, invoices: List[Invoice], from_date: date
    ) -> List[Invoice]:
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
        except Exception:
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

    def run(
        self,
        source_name: str,
        from_date: date,
        email_sender_from: Optional[str] = None,
        email_subject_contains: Optional[str] = None,
        max_results: int = 30,
        extraction_params: Optional[Dict[str, Any]] = None,
    ) -> List[Invoice]:
        if source_name == "FreeInvoice":
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
                    logger.warning(
                        f"Téléchargement via 'download_invoices_from' a échoué: {e}"
                    )

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

        if source_name == "FreeMobileInvoice":
            downloader = FreeMobileInvoiceDownloader(
                login=os.getenv("FREE_MOBILE_LOGIN"),
                password=os.getenv("FREE_MOBILE_PASSWORD"),
                gmail_credentials_path=os.getenv(
                    "GMAIL_CREDENTIALS_PATH", "gmail.json"
                ),
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

        if source_name == "Gmail":
            if not self.gmail:
                logger.error("GmailManager non initialisé")
                return []

            if not extraction_params:
                logger.error("Extraction params non fournis")
                return []

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

            source = None
            pattern = None
            for source_expected, source_actual in {
                "email_html": "body_html",
                "email_text": "body_text",
            }.items():
                if isinstance(extraction_params.get(source_expected), str):
                    source = source_actual
                    pattern = re.compile(
                        self._convert_named_groups(
                            extraction_params.get(source_expected)
                        ),
                        re.DOTALL,
                    )
                    logger.info(f"Regex '{source_expected}' valide: {pattern}")
                    break
            if not pattern:
                logger.error("Aucun pattern valide trouvé")
                return []

            extracted_invoices: List[Invoice] = []
            for email in emails:
                body = email.get(source) or ""
                logger.info(f"Body: {body}")
                date_email = email.get("date") or ""
                logger.info(f"Date email: {date_email}")
                if pattern:
                    try:
                        for m in pattern.finditer(body):
                            logger.info(f"Match: {m.groupdict()}")
                            inv_id = m.groupdict().get("invoice_id") or None
                            date_raw = m.groupdict().get("date") or date_email
                            amount_text = m.groupdict().get("amount_text") or None
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
                        logger.warning(
                            f"Erreur lors de l'extraction HTML sur l'email {email.get('id')}: {e}"
                        )

            # Télécharger pièces jointes pour information/archivage
            saved = self.gmail.download_attachments_from_emails(emails, self.output_dir)
            logger.info(f"Pièces jointes téléchargées: {saved}")

            # Filtrer par date
            filtered_invoices = self._filter_invoices_from_date(
                extracted_invoices, from_date
            )

            return filtered_invoices

        logger.error(f"Source inconnue: {source_name}")
        return []
