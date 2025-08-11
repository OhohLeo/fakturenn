#!/usr/bin/env python3
import os
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

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
