#!/usr/bin/env python3
import os
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

# Helpers
from app.core.date_utils import (
    extract_month_from_invoice_date,
    parse_date_label_to_date,
)
from app.core.paheko_helpers import (
    PahekoMapping,
    parse_transaction_fields,
    build_paheko_lines_if_needed,
)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class EmailSearchCriteria:
    sender_from: str
    subject_contains: str
    max_results: int = 30


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
        query = f"is:unread from:{sender_from} subject:'{subject_contains}'"
        return self.gmail.search_emails(query, max_results=max_results) or []

    def _filter_invoices_from_date(
        self, invoices: List[Invoice], from_date: date
    ) -> List[Invoice]:
        filtered: List[Invoice] = []
        for inv in invoices:
            inv_dt = parse_date_label_to_date(inv.date or "")
            if inv_dt and inv_dt >= from_date:
                filtered.append(inv)
        return filtered

    def run_source(
        self, source_name: str, from_date: date
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
                # 1) Lancer le téléchargement via l'API unifiée from-date
                from_date_str = from_date.strftime("%Y-%m-%d")
                try:
                    _, _ = downloader.download_invoices_from(from_date_str)
                except Exception as e:
                    logger.warning(
                        f"Téléchargement via 'download_invoices_from' a échoué: {e}"
                    )

                # 2) Construire la liste des factures trouvées (filtrées) sans re-télécharger
                invoices: List[Invoice] = []
                current_year = datetime.now().year
                for y in range(from_date.year, current_year + 1):
                    try:
                        invs = downloader.get_invoices_by_year(y)
                        invoices.extend(invs)
                    except Exception:
                        continue
                invoices = self._filter_invoices_from_date(invoices, from_date)

                # 3) Déterminer celles réellement téléchargées en vérifiant les fichiers existants
                downloaded_invoices: List[Invoice] = []
                for inv in invoices:
                    filename = inv.suggested_filename(prefix="Free")
                    filepath = os.path.join(self.output_dir, filename)
                    if os.path.exists(filepath):
                        downloaded_invoices.append(inv)

                return (
                    len(invoices),
                    len(downloaded_invoices),
                    invoices,
                    downloaded_invoices,
                )
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
            try:
                from_date_str = from_date.strftime("%Y-%m-%d")
                invoices = downloader.get_invoices_list(from_date=from_date_str)
                filtered = self._filter_invoices_from_date(invoices, from_date)
                downloaded = 0
                downloaded_invoices: List[Invoice] = []
                for inv in filtered:
                    if downloader.download_invoice(inv):
                        downloaded += 1
                        downloaded_invoices.append(inv)
                return (len(filtered), downloaded, filtered, downloaded_invoices)
            finally:
                downloader.close()

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

        label = mapping.label_template.format(**{k: str(v) for k, v in context.items()})
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

            # Détection de doublon: vérifier le journal du compte référencé pour une écriture même date/libellé
            account_code_to_check = first_debit or first_credit
            if account_code_to_check:
                try:
                    journal = self.paheko.get_account_journal(
                        id_year=id_year, code=account_code_to_check
                    )

                    def normalize_date(value: object) -> Optional[str]:
                        if isinstance(value, str):
                            return value[:10]
                        if isinstance(value, dict):
                            inner = value.get("date")  # type: ignore[attr-defined]
                            if isinstance(inner, str):
                                return inner[:10]
                        return None

                    target_date = payload["date"]
                    for entry in journal or []:
                        entry_date = normalize_date(entry.get("date"))  # type: ignore[arg-type]
                        entry_label = (
                            entry.get("label") if isinstance(entry, dict) else None
                        )  # type: ignore[arg-type]
                        if entry_date == target_date and entry_label == label:
                            logger.info(
                                f"Écriture déjà présente pour le compte {account_code_to_check} à la date {target_date} avec le libellé '{label}'. Export ignoré."
                            )
                            return None
                except Exception as e:
                    logger.warning(
                        f"Impossible de vérifier les doublons sur le journal du compte {account_code_to_check}: {e}"
                    )

            logger.info(f"Création d'une écriture Paheko: {payload}")
            tx = self.paheko.create_transaction(**payload)
            logger.info(f"Transaction Paheko créée: {tx.get('id')}")
            return tx
        except Exception as e:
            logger.error(f"Erreur export Paheko: {e}")
            return None

    def run(self, from_date: str, max_results: int = 30) -> None:
        configs = self.load_config()
        if not configs:
            logger.warning("Aucune configuration à traiter")
            return

        # Parse from_date
        parsed_from: Optional[date] = parse_date_label_to_date(from_date)
        if not parsed_from:
            logger.error(
                f"Date invalide pour --from: '{from_date}'. Exemples valides: 2024-01-01, 2024-01, 01/2024, 'Janvier 2024'"
            )
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

            mapping = PahekoMapping(
                type=cfg.paheko_type,
                label_template=cfg.paheko_label,
                debit=cfg.paheko_debit,
                credit=cfg.paheko_credit,
            )

            # Run source
            total, downloaded, invoices, downloaded_invoices = self.run_source(
                cfg.fakturenn_extraction, parsed_from
            )
            logger.info(f"Source exécutée: total={total} téléchargées={downloaded}")

            # Export one entry per downloaded invoice
            for inv in downloaded_invoices:
                inv_month_label = extract_month_from_invoice_date(inv.date or "")
                invoice_id_for_context = inv.invoice_id or ""
                context = {
                    "invoice_id": invoice_id_for_context,
                    "month": inv_month_label,
                }

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
