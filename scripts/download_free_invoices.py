#!/usr/bin/env python3
"""
Script d'exemple pour télécharger les factures Free
Utilise le module free.py pour récupérer les factures
"""

import os
import sys
import logging
from pathlib import Path
import argparse

# Ajout du répertoire parent au path pour importer les modules
sys.path.append(str(Path(__file__).parent.parent))

from app.sources.free import FreeInvoiceDownloader

# Configuration du logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_env_file():
    """Charge les variables d'environnement depuis le fichier .env"""
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
        logger.info("✅ Variables d'environnement chargées")
    else:
        logger.warning(f"Fichier .env non trouvé: {env_path}")


def clean_credentials(credential):
    """Nettoie les identifiants des caractères invisibles"""
    if credential:
        cleaned = credential.strip()
        cleaned = cleaned.encode("ascii", "ignore").decode("ascii").strip()
        return cleaned
    return credential


def main():
    """Fonction principale"""
    load_env_file()

    parser = argparse.ArgumentParser(
        description="Télécharge les factures Free à partir d'une date donnée",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        required=False,
        default=os.getenv("FROM_DATE", "").strip(),
        help="Date à partir de laquelle récupérer les factures (ex: 2024-01-01, 2024-01, 01/2024, 'Janvier 2024')",
    )
    args = parser.parse_args()

    LOGIN = os.getenv("FREE_LOGIN", "fbx12345678")
    PASSWORD = os.getenv("FREE_PASSWORD", "votre_mot_de_passe")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "factures_free")

    # Nettoyage des identifiants
    LOGIN = clean_credentials(LOGIN)
    PASSWORD = clean_credentials(PASSWORD)

    # Vérification des paramètres
    if LOGIN == "fbx12345678" or PASSWORD == "votre_mot_de_passe":
        logger.error("Veuillez configurer vos identifiants dans le fichier .env")
        logger.info("Variables requises dans .env:")
        logger.info("1. FREE_LOGIN: Votre identifiant Free (Freebox)")
        logger.info("2. FREE_PASSWORD: Votre mot de passe Free")
        logger.info("3. OUTPUT_DIR: Répertoire de sortie (optionnel)")
        return

    if not args.from_date:
        logger.error("--from est requis (ou variable d'environnement FROM_DATE)")
        return

    downloader = FreeInvoiceDownloader(
        auto_auth=True,
        login=LOGIN,
        password=PASSWORD,
        output_dir=OUTPUT_DIR,
    )

    total, downloaded = downloader.download_invoices_from(args.from_date)
    if downloaded > 0:
        logger.info(
            f"✅ {downloaded}/{total} factures téléchargées avec succès (>= {args.from_date})"
        )
    else:
        logger.warning(
            f"❌ Aucune facture n'a pu être téléchargée à partir de {args.from_date}"
        )

    downloader.close()


if __name__ == "__main__":
    main()
