#!/usr/bin/env python3
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, date

from app.sources.gmail_manager import GmailManager
from app.core.google_sheets import GoogleSheetsConfigLoader, FakturennConfigRow
from app.export.paheko import PahekoClient
from app.sources.runner import SourceRunner

# Helpers
from app.core.date_utils import (
    extract_month_and_year_from_invoice_date,
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
        self.source_runner = SourceRunner(
            output_dir=self.output_dir, gmail_manager=self.gmail
        )

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
                "date": context.get("date", datetime.now().strftime("%Y-%m-%d")),
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

    def run(
        self, from_date: str, max_results: int = 30, origins: Optional[List[str]] = None
    ) -> None:
        configs = self.load_config()
        if not configs:
            logger.warning("Aucune configuration à traiter")
            return

        # Filter configs by origins if provided
        if origins:
            normalized_origins = {o.strip().lower() for o in origins if o.strip()}
            configs = [
                c
                for c in configs
                if (c.origin or "").strip().lower() in normalized_origins
            ]
            if not configs:
                logger.info("Aucune configuration ne correspond aux origines fournies")
                return

        # Parse from_date
        parsed_from: date | None = parse_date_label_to_date(from_date)
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
                return

        for cfg in configs:
            logger.info(
                f"Traitement config: origin={cfg.origin} from={cfg.sender_from} subject~='{cfg.subject}' source={cfg.fakturenn_extraction}"
            )

            mapping = PahekoMapping(
                type=cfg.paheko_type,
                label_template=cfg.paheko_label,
                debit=cfg.paheko_debit,
                credit=cfg.paheko_credit,
            )

            downloaded_invoices = self.source_runner.run(
                cfg.fakturenn_extraction,
                parsed_from,
                email_sender_from=cfg.sender_from,
                email_subject_contains=cfg.subject,
                max_results=max_results,
                extraction_params=getattr(cfg, "fakturenn_extraction_params", {}) or {},
            )
            logger.info(f"Source exécutée: téléchargées={len(downloaded_invoices)}")

            for invoice in downloaded_invoices:
                invoice_date = parse_date_label_to_date(invoice.date or "")
                invoice_date_str = (
                    invoice_date.strftime("%Y-%m-%d") if invoice_date else ""
                )
                inv_month_label, inv_year, inv_quarter = (
                    extract_month_and_year_from_invoice_date(invoice.date or "")
                )
                inv_year_str = str(inv_year) if inv_year is not None else ""
                invoice_id_for_context = invoice.invoice_id or ""
                context = {
                    "invoice_id": invoice_id_for_context,
                    "month": inv_month_label,
                    "date": invoice_date_str,
                    "year": inv_year_str,
                    "quarter": inv_quarter,
                }

                inv_dt = parse_date_label_to_date(invoice.date or "")
                if not inv_dt:
                    logger.warning(
                        f"Date de facture invalide ou introuvable ('{invoice.date}'), export ignoré"
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
                        f"Aucun exercice Paheko ne couvre la date {invoice.date} ({inv_dt}), export ignoré"
                    )
                    continue

                if invoice.amount_eur is None or invoice.amount_eur <= 0:
                    logger.warning(
                        f"Montant de facture invalide ou nul ('{invoice.amount_eur}'), export ignoré"
                    )
                    continue

                id_year = (
                    matching_year.get("id") if isinstance(matching_year, dict) else None
                )
                self.export_to_paheko(
                    mapping=mapping,
                    context=context,
                    amount_eur=invoice.amount_eur,
                    id_year=id_year,
                )
