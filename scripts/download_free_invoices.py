#!/usr/bin/env python3
"""
Script d'exemple pour télécharger les factures Free
Utilise le module free.py pour récupérer les factures
"""

import os
import sys
import logging
from pathlib import Path

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


def download_latest_invoice():
    """Télécharge la dernière facture"""
    logger.info("=== TÉLÉCHARGEMENT DE LA DERNIÈRE FACTURE ===")

    downloader = FreeInvoiceDownloader(
        auto_auth=True,
        login=LOGIN,
        password=PASSWORD,
        output_dir=OUTPUT_DIR,
    )

    success = downloader.download_latest_invoice()
    if success:
        logger.info("✅ Dernière facture téléchargée avec succès")
    else:
        logger.error("❌ Échec du téléchargement de la dernière facture")


def download_invoices_by_year(year):
    """Télécharge toutes les factures d'une année"""
    logger.info(f"=== TÉLÉCHARGEMENT DES FACTURES DE {year} ===")

    downloader = FreeInvoiceDownloader(
        auto_auth=True,
        login=LOGIN,
        password=PASSWORD,
        output_dir=OUTPUT_DIR,
    )

    total, downloaded = downloader.download_invoices_by_year(year)
    if downloaded > 0:
        logger.info(f"✅ {downloaded} factures téléchargées avec succès pour {year}")
    else:
        logger.warning(f"❌ Aucune facture n'a pu être téléchargée pour {year}")


def main():
    """Fonction principale"""
    global LOGIN, PASSWORD, OUTPUT_DIR

    # Chargement des variables d'environnement
    load_env_file()

    # Configuration depuis .env
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

    # Menu interactif
    print("\n=== TÉLÉCHARGEUR DE FACTURES FREE ===")
    print("1. Télécharger la dernière facture")
    print("2. Télécharger toutes les factures d'une année")
    print("3. Quitter")

    while True:
        choice = input("\nChoisissez une option (1-3): ").strip()

        if choice == "1":
            download_latest_invoice()
            break
        elif choice == "2":
            try:
                year = int(input("Entrez l'année (ex: 2025): ").strip())
                download_invoices_by_year(year)
            except ValueError:
                logger.error("Année invalide")
            break
        elif choice == "3":
            logger.info("Au revoir !")
            break
        else:
            print("Option invalide. Veuillez choisir 1, 2 ou 3.")


if __name__ == "__main__":
    main()
