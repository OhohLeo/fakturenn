#!/usr/bin/env python3
import os
import logging
from typing import List, Optional
from dataclasses import dataclass

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


logger = logging.getLogger(__name__)

# Minimal scopes to read Google Sheets
SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


@dataclass
class FakturennConfigRow:
    origin: str
    sender_from: str
    subject: str
    fakturenn_extraction: str
    paheko_type: str
    paheko_label: str
    paheko_debit: str
    paheko_credit: str


class GoogleSheetsConfigLoader:
    """
    Loads Fakturenn configuration from a Google Sheets spreadsheet.

    Expected header (new format only):
    origin | from | subject | fakturenn_extraction | paheko_type | paheko_label | paheko_debit | paheko_credit
    """

    def __init__(
        self,
        spreadsheet_id: str,
        range_name: str,
        credentials_path: str = "google.json",
        token_path: str = "sheets.json",
    ) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.range_name = range_name
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None

    def _ensure_service(self) -> None:
        if self.service is not None:
            return
        creds: Optional[Credentials] = None

        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(
                    self.token_path, SHEETS_SCOPES
                )
                logger.info("Token Google Sheets chargé depuis le fichier")
            except Exception as e:
                logger.warning(f"Erreur lors du chargement du token Sheets: {e}")
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Token Sheets rafraîchi avec succès")
                except Exception as e:
                    logger.error(
                        f"Erreur lors du rafraîchissement du token Sheets: {e}"
                    )
                    creds = None

            if not creds:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Fichier credentials.json non trouvé: {self.credentials_path}\n"
                        "Créez des identifiants OAuth2 et téléchargez le fichier depuis Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SHEETS_SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save token
            with open(self.token_path, "w") as token_file:
                token_file.write(creds.to_json())

        self.service = build("sheets", "v4", credentials=creds)

    def fetch_rows(self) -> List[FakturennConfigRow]:
        self._ensure_service()
        sheet = self.service.spreadsheets()
        result = (
            sheet.values()
            .get(spreadsheetId=self.spreadsheet_id, range=self.range_name)
            .execute()
        )
        values: List[List[str]] = result.get("values", [])

        config_rows: List[FakturennConfigRow] = []
        if not values:
            logger.warning("Aucune configuration trouvée dans Google Sheets")
            return config_rows

        def normalize(s: str) -> str:
            return s.strip().lower().replace(" ", "_")

        # Require header row with new format
        first_row = [normalize(c) for c in values[0]] if values else []
        expected_keys = [
            "origin",
            "from",
            "subject",
            "fakturenn_extraction",
            "paheko_type",
            "paheko_label",
            "paheko_debit",
            "paheko_credit",
        ]
        header_line = ",".join(first_row)
        if not all(k in header_line for k in expected_keys):
            raise ValueError(
                "En-tête invalide: le format attendu est 'origin, from, subject, fakturenn_extraction, paheko_type, paheko_label, paheko_debit, paheko_credit'"
            )

        header_map = {name: first_row.index(name) for name in expected_keys}

        def cell(row: List[str], name: str) -> str:
            idx = header_map[name]
            return row[idx].strip() if idx < len(row) else ""

        for row in values[1:]:
            origin = cell(row, "origin")
            sender_from = cell(row, "from")
            subject = cell(row, "subject")
            fakturenn_extraction = cell(row, "fakturenn_extraction")
            paheko_type = cell(row, "paheko_type")
            paheko_label = cell(row, "paheko_label")
            paheko_debit = cell(row, "paheko_debit")
            paheko_credit = cell(row, "paheko_credit")

            config_rows.append(
                FakturennConfigRow(
                    origin=origin,
                    sender_from=sender_from,
                    subject=subject,
                    fakturenn_extraction=fakturenn_extraction,
                    paheko_type=paheko_type,
                    paheko_label=paheko_label,
                    paheko_debit=paheko_debit,
                    paheko_credit=paheko_credit,
                )
            )

        return config_rows
