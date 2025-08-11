#!/usr/bin/env python3
import os
import argparse
import logging
from pathlib import Path

from app.core.runner import FakturennRunner


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_env_file():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        logger.info(f"Chargement des variables depuis {env_path}")
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    value = value.encode("ascii", "ignore").decode("ascii").strip()
                    os.environ[key] = value


def main():
    load_env_file()

    parser = argparse.ArgumentParser(
        description="Fakturenn Runner: lit la config depuis Google Sheets, écoute la boite mail et télécharge/exporte",
    )
    parser.add_argument("--mode", choices=["latest", "year"], default="latest")
    parser.add_argument("--year", type=int, help="Année à traiter si mode=year")
    parser.add_argument(
        "--max", type=int, default=30, help="Nb maximum d'emails à lire par filtre"
    )
    parser.add_argument(
        "--sheets-id",
        required=False,
        default=os.getenv("SHEETS_SPREADSHEET_ID", ""),
        help="ID du Google Spreadsheet",
    )
    parser.add_argument(
        "--sheets-range",
        required=False,
        default=os.getenv("SHEETS_RANGE", "Config!A:F"),
        help="Plage (ex: 'Config!A:F')",
    )
    parser.add_argument(
        "--sheets-credentials", default=os.getenv("SHEETS_CREDENTIALS", "google.json")
    )
    parser.add_argument(
        "--sheets-token", default=os.getenv("SHEETS_TOKEN", "sheets.json")
    )

    parser.add_argument(
        "--gmail-credentials", default=os.getenv("GMAIL_CREDENTIALS_PATH", "gmail.json")
    )
    parser.add_argument(
        "--gmail-token", default=os.getenv("GMAIL_TOKEN_PATH", "gmail.json")
    )

    parser.add_argument("--paheko-base", default=os.getenv("PAHEKO_BASE_URL", ""))
    parser.add_argument("--paheko-user", default=os.getenv("PAHEKO_USER", ""))
    parser.add_argument("--paheko-pass", default=os.getenv("PAHEKO_PASS", ""))

    parser.add_argument("--output-dir", default=os.getenv("OUTPUT_DIR", "factures"))

    args = parser.parse_args()

    if args.mode == "year" and not args.year:
        parser.error("--year est requis lorsque --mode=year")

    if not args.sheets_id:
        parser.error(
            "--sheets-id est requis (ou variable d'environnement SHEETS_SPREADSHEET_ID)"
        )

    runner = FakturennRunner(
        sheets_spreadsheet_id=args.sheets_id,
        sheets_range=args.sheets_range,
        sheets_credentials_path=args.sheets_credentials,
        sheets_token_path=args.sheets_token,
        gmail_credentials_path=args.gmail_credentials,
        gmail_token_path=args.gmail_token,
        paheko_base_url=args.paheko_base or None,
        paheko_username=args.paheko_user or None,
        paheko_password=args.paheko_pass or None,
        output_dir=args.output_dir,
    )

    runner.run(mode=args.mode, year=args.year, max_results=args.max)


if __name__ == "__main__":
    main()
