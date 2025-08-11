#!/usr/bin/env python3
import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, date

from app.sources.gmail_manager import GmailManager
from app.core.google_sheets import GoogleSheetsConfigLoader, FakturennConfigRow
from app.sources.free import FreeInvoiceDownloader
from app.sources.free_mobile import FreeMobileInvoiceDownloader
from app.sources.invoice import Invoice
from app.export.paheko import PahekoClient


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class PahekoMapping:
    type: str
    label_template: str
    debit: str
    credit: str

    def parse(
        self,
    ) -> Tuple[Optional[str], Optional[float], Optional[str], Optional[str]]:
        # Parsing to be done at usage time; this dataclass mainly stores raw values
        return None, None, None, None


def parse_transaction_field(tx_field: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse a paheko_transaction like "626:debit" to (account_debit, account_credit)
    - Accepts multiple entries separated by newlines/commas/semicolons.
    - Returns the first debit and the first credit accounts found.
    """
    if not tx_field:
        return None, None

    debit_account: Optional[str] = None
    credit_account: Optional[str] = None

    # Split on newlines, commas, or semicolons
    parts = re.split(r"[\r\n;,]+", tx_field)
    for raw in parts:
        part = raw.strip()
        if not part:
            continue
        m = re.match(r"\s*([0-9A-Za-z]+)\s*:\s*(debit|credit)\s*$", part)
        if not m:
            continue
        account = m.group(1)
        side = m.group(2)
        if side == "debit" and debit_account is None:
            debit_account = account
        elif side == "credit" and credit_account is None:
            credit_account = account
        # Stop early if we have both
        if debit_account and credit_account:
            break

    return debit_account, credit_account


def parse_transaction_fields(
    debit_field: str, credit_field: str
) -> Tuple[List[str], List[str]]:
    """
    Split debit and credit account lists from two separate fields.
    Accepts separators: newlines, commas, semicolons. Returns ordered lists.
    """

    def split_accounts(value: str) -> List[str]:
        if not value:
            return []
        parts = re.split(r"[\r\n;,]+", value)
        return [p.strip() for p in parts if p and p.strip()]

    return split_accounts(debit_field), split_accounts(credit_field)


def format_label(template: str, context: Dict[str, str]) -> str:
    label = template
    for key, value in context.items():
        label = label.replace("{" + key + "}", str(value))
    return label


FRENCH_MONTHS = {
    "01": "Janvier",
    "02": "Février",
    "03": "Mars",
    "04": "Avril",
    "05": "Mai",
    "06": "Juin",
    "07": "Juillet",
    "08": "Août",
    "09": "Septembre",
    "10": "Octobre",
    "11": "Novembre",
    "12": "Décembre",
}

FRENCH_MONTH_NAMES = {v.lower(): v for v in FRENCH_MONTHS.values()}

# Map lowercased French month name to month number ("01".."12")
FRENCH_MONTH_NAME_TO_NUM: Dict[str, str] = {
    name.lower(): num for num, name in FRENCH_MONTHS.items()
}


def extract_month_from_invoice_date(date_label: str) -> str:
    """Return a month label (French) extracted from a human date string.

    Strategies:
    - If a French month name appears in the label, return it capitalized as in canonical map
    - Else if we detect numeric formats like YYYY-MM, YYYY/MM, MM/YYYY, map to French name
    - Else return the original label (last resort)
    """
    if not date_label:
        return ""

    lower = date_label.lower()
    for name_lower, canonical in FRENCH_MONTH_NAMES.items():
        if name_lower in lower:
            return canonical

    # Try numeric patterns
    m = re.search(r"(?P<y>\d{4})[-/](?P<m>\d{2})", date_label)
    if m:
        num = m.group("m")
        return FRENCH_MONTHS.get(num, date_label)

    m = re.search(r"(?P<m>\d{2})[-/](?P<y>\d{4})", date_label)
    if m:
        num = m.group("m")
        return FRENCH_MONTHS.get(num, date_label)

    return date_label


def parse_date_label_to_date(date_label: str) -> Optional[date]:
    """Parse various invoice date labels to a concrete date.

    Supported patterns:
    - "YYYY-MM-DD" -> that exact date
    - "YYYY-MM" or "YYYY/MM" -> first day of that month
    - "MM/YYYY" -> first day of that month
    - French month name + year, e.g. "Janvier 2025" -> first day of that month
    - Bare year "YYYY" -> January 1st of that year
    """
    if not date_label:
        return None

    txt = date_label.strip()

    # YYYY-MM-DD
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", txt)
    if m:
        try:
            return datetime.strptime(m.group(0).replace("/", "-"), "%Y-%m-%d").date()
        except Exception:
            pass

    # YYYY-MM or YYYY/MM
    m = re.search(r"(\d{4})[-/](\d{2})", txt)
    if m:
        y, mm = int(m.group(1)), int(m.group(2))
        try:
            return date(y, mm, 1)
        except Exception:
            return None

    # MM/YYYY
    m = re.search(r"(\d{2})[-/](\d{4})", txt)
    if m:
        mm, y = int(m.group(1)), int(m.group(2))
        try:
            return date(y, mm, 1)
        except Exception:
            return None

    # French month name + year (order-insensitive checks)
    year_match = re.search(r"(\d{4})", txt)
    if year_match:
        y = int(year_match.group(1))
        lower = txt.lower()
        for name_lower, mm_str in FRENCH_MONTH_NAME_TO_NUM.items():
            if name_lower in lower:
                try:
                    return date(y, int(mm_str), 1)
                except Exception:
                    return None
        # If only year present
        try:
            return date(y, 1, 1)
        except Exception:
            return None

    return None


def build_paheko_lines_if_needed(
    mapping: PahekoMapping, amount_eur: Optional[float]
) -> Dict:
    debit_list, credit_list = parse_transaction_fields(mapping.debit, mapping.credit)
    first_debit = debit_list[0] if debit_list else None
    first_credit = credit_list[0] if credit_list else None
    payload: Dict = {}

    if first_debit and first_credit:
        if amount_eur is not None:
            payload.update(
                {"amount": amount_eur, "debit": first_debit, "credit": first_credit}
            )
    elif first_debit or first_credit:
        if amount_eur is not None:
            payload.update({"amount": amount_eur})
            if first_debit:
                payload["debit"] = first_debit
            if first_credit:
                payload["credit"] = first_credit

    return payload


class FakturennRunner:
    def __init__(
        self,
        sheets_spreadsheet_id: str,
        sheets_range: str,
        sheets_credentials_path: str = "google.json",
        sheets_token_path: str = "sheets.json",
        gmail_credentials_path: str = "gmail.json",
        gmail_token_path: str = "gmail.json",
        paheko_base_url: Optional[str] = None,
        paheko_username: Optional[str] = None,
        paheko_password: Optional[str] = None,
        output_dir: str = "factures",
    ) -> None:
        self.sheets_loader = GoogleSheetsConfigLoader(
            spreadsheet_id=sheets_spreadsheet_id,
            range_name=sheets_range,
            credentials_path=sheets_credentials_path,
            token_path=sheets_token_path,
        )
        self.gmail = GmailManager(
            credentials_path=gmail_credentials_path, token_path=gmail_token_path
        )
        self.output_dir = output_dir

        # Paheko client optional
        self.paheko: Optional[PahekoClient] = None
        if paheko_base_url and paheko_username and paheko_password:
            logger.info(
                f"Initialisation de Paheko avec: {paheko_base_url}, {paheko_username}, {paheko_password}"
            )
            self.paheko = PahekoClient(
                paheko_base_url, paheko_username, paheko_password
            )

    def load_config(self) -> List[FakturennConfigRow]:
        return self.sheets_loader.fetch_rows()

    def find_unread_matching(
        self, sender_from: str, subject_contains: str, max_results: int = 30
    ) -> List[Dict]:
        # Gmail query using from and subject
        query = f"is:unread from:{sender_from} subject:'{subject_contains}'"
        return self.gmail.search_emails(query, max_results=max_results) or []

    def run_source(
        self, source_name: str, mode: str, year: Optional[int]
    ) -> Tuple[int, int, List[Invoice], List[Invoice]]:
        # Return (total_found, total_downloaded, invoices_found, invoices_downloaded)
        if source_name == "FreeInvoiceDownloader":
            downloader = FreeInvoiceDownloader(
                auto_auth=True,
                login=os.getenv("FREE_LOGIN"),
                password=os.getenv("FREE_PASSWORD"),
                output_dir=self.output_dir,
                headless=os.getenv("HEADLESS_MODE", "true").lower() == "true",
            )
            try:
                invoices: List[Invoice] = []
                downloaded_invoices: List[Invoice] = []
                if mode == "latest":
                    inv = downloader.get_latest_invoice()
                    if not inv:
                        return (0, 0, [], [])
                    ok = downloader.download_invoice(inv)
                    invoices = [inv]
                    if ok:
                        downloaded_invoices = [inv]
                    return (1, 1 if ok else 0, invoices, downloaded_invoices)
                elif mode == "year" and year is not None:
                    invoices = downloader.get_invoices_by_year(year)
                    downloaded = 0
                    for inv in invoices:
                        if downloader.download_invoice(inv):
                            downloaded += 1
                            downloaded_invoices.append(inv)
                    return (len(invoices), downloaded, invoices, downloaded_invoices)
                else:
                    logger.warning(f"Mode inconnu ou année manquante: {mode}")
                    return (0, 0, [], [])
            finally:
                downloader.close()

        if source_name == "FreeMobileInvoiceDownloader":
            downloader = FreeMobileInvoiceDownloader(
                auto_auth=True,
                login=os.getenv("FREE_MOBILE_LOGIN"),
                password=os.getenv("FREE_MOBILE_PASSWORD"),
                gmail_credentials_path=os.getenv(
                    "GMAIL_CREDENTIALS_PATH", "gmail.json"
                ),
                gmail_token_path=os.getenv("GMAIL_TOKEN_PATH", "gmail.json"),
                output_dir=self.output_dir,
            )
            import asyncio

            if mode == "latest":
                # Free Mobile exposes only list-all; approximate latest by fetching list and downloading first
                async def run_latest():
                    invoices = await downloader.get_invoices_list()
                    if not invoices:
                        return (0, 0, [], [])
                    inv = invoices[0]
                    ok = downloader.download_invoice(inv)
                    return (1, 1 if ok else 0, [inv], [inv] if ok else [])

                return asyncio.run(run_latest())
            elif mode == "year" and year is not None:

                async def run_year():
                    invoices = await downloader.get_invoices_list()
                    filtered = [i for i in invoices if str(year) in (i.date or "")]
                    downloaded = 0
                    downloaded_invoices: List[Invoice] = []
                    for inv in filtered:
                        if downloader.download_invoice(inv):
                            downloaded += 1
                            downloaded_invoices.append(inv)
                    return (len(filtered), downloaded, filtered, downloaded_invoices)

                return asyncio.run(run_year())
            else:
                logger.warning(f"Mode inconnu ou année manquante: {mode}")
                return (0, 0, [], [])

        logger.error(f"Source inconnue: {source_name}")
        return (0, 0, [], [])

    def export_to_paheko(
        self,
        mapping: PahekoMapping,
        context: Dict[str, str],
        amount_eur: Optional[float] = None,
        id_year: Optional[int] = None,
    ) -> Optional[Dict]:
        if not self.paheko:
            logger.info("Paheko non configuré, export ignoré")
            return None

        if not id_year or id_year <= 0:
            logger.warning(
                "Aucun exercice Paheko sélectionné (id_year manquant), export ignoré"
            )
            return None

        label = format_label(mapping.label_template, context)
        debit_list, credit_list = parse_transaction_fields(
            mapping.debit, mapping.credit
        )
        first_debit = debit_list[0] if debit_list else None
        first_credit = credit_list[0] if credit_list else None
        try:
            payload = {
                "id_year": id_year,
                "label": label,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "transaction_type": mapping.type,
            }
            payload.update(build_paheko_lines_if_needed(mapping, amount_eur))
            if first_debit and not payload.get("debit"):
                payload["debit"] = first_debit
            if first_credit and not payload.get("credit"):
                payload["credit"] = first_credit

            logger.info(f"Création d'une écriture Paheko: {payload}")
            tx = self.paheko.create_transaction(**payload)
            logger.info(f"Transaction Paheko créée: {tx.get('id')}")
            return tx
        except Exception as e:
            logger.error(f"Erreur export Paheko: {e}")
            return None

    def run(self, mode: str, year: Optional[int] = None, max_results: int = 30) -> None:
        configs = self.load_config()
        if not configs:
            logger.warning("Aucune configuration à traiter")
            return

        # Précharger les exercices Paheko si disponible
        paheko_years: List[Dict] = []
        if self.paheko:
            try:
                paheko_years = self.paheko.get_accounting_years() or []
            except Exception as e:
                logger.error(f"Impossible de récupérer les exercices Paheko: {e}")
                paheko_years = []

        for cfg in configs:
            logger.info(
                f"Traitement config: from={cfg.sender_from} subject~='{cfg.subject}' source={cfg.fakturenn_extraction}"
            )
            emails = self.find_unread_matching(
                cfg.sender_from, cfg.subject, max_results
            )
            if not emails:
                logger.info("Aucun email non lu correspondant")
                continue

            # Contexte générique pour libellé
            month = ""

            mapping = PahekoMapping(
                type=cfg.paheko_type,
                label_template=cfg.paheko_label,
                debit=cfg.paheko_debit,
                credit=cfg.paheko_credit,
            )

            # Run source
            total, downloaded, invoices, downloaded_invoices = self.run_source(
                cfg.fakturenn_extraction, mode, year
            )
            logger.info(f"Source exécutée: total={total} téléchargées={downloaded}")

            # Export one entry per downloaded invoice
            for inv in downloaded_invoices:
                logger.info(f"Invoice: {inv}")
                month = extract_month_from_invoice_date(inv.date or "")
                invoice_id_for_context = inv.invoice_id or ""
                context = {
                    "invoice_id": invoice_id_for_context,
                    "month": month,
                }

                # Déterminer l'exercice Paheko correspondant à la date de la facture
                inv_dt = parse_date_label_to_date(inv.date or "")
                if not inv_dt:
                    logger.warning(
                        f"Date de facture invalide ou introuvable ('{inv.date}'), export ignoré"
                    )
                    continue

                matching_year: Optional[Dict] = None
                for y in paheko_years:
                    try:
                        y_start = datetime.strptime(
                            y.get("start_date", ""), "%Y-%m-%d"
                        ).date()
                        y_end = datetime.strptime(
                            y.get("end_date", ""), "%Y-%m-%d"
                        ).date()
                    except Exception:
                        continue
                    if y_start <= inv_dt <= y_end:
                        matching_year = y
                        break

                if not matching_year:
                    logger.warning(
                        f"Aucun exercice Paheko ne couvre la date {inv.date} ({inv_dt}), export ignoré"
                    )
                    continue

                self.export_to_paheko(
                    mapping,
                    context,
                    amount_eur=inv.amount_eur,
                    id_year=int(matching_year.get("id")),
                )

            # Optionally mark emails as read
            try:
                message_ids = [e["id"] for e in emails]
                self.gmail.mark_as_read(message_ids)
            except Exception:
                pass
