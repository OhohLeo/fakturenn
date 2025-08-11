#!/usr/bin/env python3
"""
Script pour télécharger les factures Free Mobile
Utilise BeautifulSoup4 pour parser la page et extraire les liens des factures
Support de l'authentification automatisée avec Selenium et Gmail Manager
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging
from typing import Optional
from pathlib import Path
import asyncio

from app.sources.free_mobile_auth import FreeMobileAuthenticator
from app.sources.invoice import Invoice


# Configuration du logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FreeMobileInvoiceDownloader:
    def __init__(
        self,
        session_id: Optional[str] = None,
        user_token: Optional[str] = None,
        selfcare_token: Optional[str] = None,
        output_dir: str = "factures_free",
        auto_auth: bool = False,
        login: Optional[str] = None,
        password: Optional[str] = None,
        gmail_credentials_path: str = "gmail.json",
        gmail_token_path: str = "gmail.json",
    ):
        """
        Initialise le téléchargeur de factures Free Mobile

        Args:
            session_id (str, optional): ACCOUNT_SESSID cookie
            user_token (str, optional): X_USER_TOKEN cookie
            selfcare_token (str, optional): SELFCARE_TOKEN cookie
            output_dir (str): Répertoire de sortie pour les factures
            auto_auth (bool): Activer l'authentification automatisée
            login (str, optional): Identifiant Free Mobile pour auto-auth
            password (str, optional): Mot de passe Free Mobile pour auto-auth
            gmail_credentials_path (str): Chemin vers credentials.json Gmail
            gmail_token_path (str): Chemin vers token.json Gmail
        """
        self.base_url = "https://mobile.free.fr"
        self.account_url = f"{self.base_url}/account/v2"
        self.output_dir = output_dir
        self.auto_auth = auto_auth
        self.login = login
        self.password = password
        self.gmail_credentials_path = gmail_credentials_path
        self.gmail_token_path = gmail_token_path

        # Création du répertoire de sortie
        os.makedirs(self.output_dir, exist_ok=True)

        # Configuration de la session
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        # Configuration des cookies si fournis
        if session_id and user_token and selfcare_token:
            self.session.cookies.set(
                "ACCOUNT_SESSID", session_id, domain="mobile.free.fr"
            )
            self.session.cookies.set(
                "X_USER_TOKEN", user_token, domain="mobile.free.fr"
            )
            self.session.cookies.set(
                "SELFCARE_TOKEN", selfcare_token, domain="mobile.free.fr"
            )
            logger.info("Cookies de session configurés manuellement")

    async def authenticate_automatically(self) -> bool:
        """
        Authentification automatisée avec Selenium et Gmail Manager (version asynchrone)

        Returns:
            bool: True si l'authentification réussit
        """
        if not self.auto_auth or not self.login or not self.password:
            logger.error(
                "Authentification automatique non configurée ou paramètres manquants"
            )
            return False

        try:
            logger.info("Début de l'authentification automatisée...")

            # Création de l'authentificateur
            authenticator = FreeMobileAuthenticator(
                gmail_credentials_path=self.gmail_credentials_path,
                gmail_token_path=self.gmail_token_path,
                headless=True,  # Mode headless pour l'automatisation
            )

            # Authentification (maintenant asynchrone)
            cookies = await authenticator.authenticate(self.login, self.password)

            if cookies:
                # Application des cookies à la session requests
                for name, value in cookies.items():
                    self.session.cookies.set(name, value, domain="mobile.free.fr")

                logger.info("✅ Authentification automatisée réussie")
                logger.info(f"Cookies appliqués: {list(cookies.keys())}")
                return True
            else:
                logger.error("❌ Échec de l'authentification automatisée")
                return False

        except Exception as e:
            logger.error(f"Erreur lors de l'authentification automatisée: {e}")
            return False

    def check_authentication(self) -> bool:
        """
        Vérifie si l'authentification est valide

        Returns:
            bool: True si authentifié, False sinon
        """
        try:
            response = self.session.get(self.account_url)

            # Vérification si on est redirigé vers la page de login
            if "login" in response.url.lower() or "connexion" in response.url.lower():
                logger.warning("Session non authentifiée ou expirée")
                return False

            # Vérification du contenu de la page
            if "Bienvenue" in response.text or "Espace Abonné" in response.text:
                logger.info("Session authentifiée valide")
                return True
            else:
                logger.warning("Session peut-être expirée")
                return False

        except Exception as e:
            logger.error(f"Erreur lors de la vérification d'authentification: {e}")
            return False

    async def ensure_authentication(self) -> bool:
        """
        S'assure que l'authentification est valide, sinon tente l'authentification automatique (version asynchrone)

        Returns:
            bool: True si authentifié, False sinon
        """
        if self.check_authentication():
            return True

        if self.auto_auth:
            logger.info("Tentative d'authentification automatique...")
            return await self.authenticate_automatically()
        else:
            logger.error("Authentification requise mais auto-auth désactivée")
            return False

    def _parse_amount_text(self, amount_text: Optional[str]) -> Optional[float]:
        if not amount_text:
            return None
        # Convert formats like "19,99€" to 19.99
        txt = amount_text.strip()
        txt = txt.replace("\xa0", " ").replace("€", "").replace(" ", "")
        txt = txt.replace(",", ".")
        try:
            return float(re.findall(r"[-+]?[0-9]*\.?[0-9]+", txt)[0])
        except Exception:
            return None

    def extract_invoice_info(self, invoice_element) -> Optional[Invoice]:
        """
        Extrait les informations d'une facture depuis un élément HTML
        """
        try:
            # Extraction de la date (mois/année)
            date_element = invoice_element.find("h3", class_="font-semibold")
            date_text = (
                date_element.get_text(strip=True) if date_element else "Date inconnue"
            )

            # Extraction du montant
            amount_element = invoice_element.find("span")
            amount_text = (
                amount_element.get_text(strip=True) if amount_element else "0,00€"
            )
            amount_eur = self._parse_amount_text(amount_text)

            # Extraction du lien de téléchargement
            download_link = None
            download_element = invoice_element.find(
                "a", href=re.compile(r"/account/v2/api/SI/invoice/\d+\?display=1")
            )
            if download_element:
                download_link = download_element.get("href")

            # Extraction du lien de visualisation
            view_link = None
            view_element = invoice_element.find(
                "a", href=re.compile(r"/account/v2/api/SI/invoice/\d+$")
            )
            if view_element:
                view_link = view_element.get("href")

            # Extraction de l'ID de facture
            invoice_id = None
            if download_link:
                match = re.search(r"/account/v2/api/SI/invoice/(\d+)", download_link)
                if match:
                    invoice_id = match.group(1)

            return Invoice(
                date=date_text,
                invoice_id=invoice_id,
                amount_text=amount_text,
                amount_eur=amount_eur,
                download_url=urljoin(self.base_url, download_link)
                if download_link
                else None,
                view_url=urljoin(self.base_url, view_link) if view_link else None,
                source="FreeMobile",
            )

        except Exception as e:
            logger.error(
                f"Erreur lors de l'extraction des informations de facture: {e}"
            )
            return None

    async def get_invoices_list(self):
        """
        Récupère la liste des factures depuis la page Free Mobile (version asynchrone)

        Returns:
            list[Invoice]: Liste des factures
        """
        try:
            # Vérification et authentification si nécessaire
            if not await self.ensure_authentication():
                logger.error("Impossible de s'authentifier")
                return []

            logger.info("Récupération de la page des factures...")
            response = self.session.get(self.account_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Recherche des éléments de facture
            invoice_elements = soup.find_all(
                "li", class_=re.compile(r"flex flex-col.*border.*bg-white")
            )

            invoices = []
            for element in invoice_elements:
                invoice = self.extract_invoice_info(element)
                if invoice:
                    invoices.append(invoice)
                    logger.info(
                        f"Facture trouvée: {invoice.date} - {invoice.amount_text}"
                    )

            logger.info(f"Total de {len(invoices)} factures trouvées")
            return invoices

        except requests.RequestException as e:
            logger.error(f"Erreur lors de la récupération de la page: {e}")
            return []
        except Exception as e:
            logger.error(f"Erreur inattendue: {e}")
            return []

    def download_invoice(self, invoice: Invoice) -> bool:
        """
        Télécharge une facture spécifique
        """
        if not invoice or not invoice.download_url:
            logger.warning(
                f"Pas d'URL de téléchargement pour la facture {getattr(invoice, 'date', 'inconnue')}"
            )
            return False

        try:
            # Génération du nom de fichier
            filename = invoice.suggested_filename(prefix="Free_Mobile")
            filepath = os.path.join(self.output_dir, filename)

            # Vérification si le fichier existe déjà
            if os.path.exists(filepath):
                logger.info(f"Fichier déjà existant: {filename}")
                return True

            logger.info(f"Téléchargement de la facture {invoice.date}...")

            # Téléchargement du PDF
            response = self.session.get(invoice.download_url)
            response.raise_for_status()

            # Sauvegarde du fichier
            with open(filepath, "wb") as f:
                f.write(response.content)

            logger.info(f"Facture téléchargée: {filename}")
            return True

        except requests.RequestException as e:
            logger.error(
                f"Erreur lors du téléchargement de la facture {getattr(invoice, 'date', 'inconnue')}: {e}"
            )
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue lors du téléchargement: {e}")
            return False

    async def download_all_invoices(self):
        """
        Télécharge toutes les factures disponibles (version asynchrone)

        Returns:
            tuple: (nombre_total, nombre_téléchargées)
        """
        invoices = await self.get_invoices_list()

        if not invoices:
            logger.warning("Aucune facture trouvée")
            return 0, 0

        downloaded_count = 0
        total_count = len(invoices)

        logger.info(f"Début du téléchargement de {total_count} factures...")

        for invoice in invoices:
            if self.download_invoice(invoice):
                downloaded_count += 1

        logger.info(
            f"Téléchargement terminé: {downloaded_count}/{total_count} factures téléchargées"
        )
        return total_count, downloaded_count


async def main():
    """
    Exemple d'utilisation asynchrone: télécharge toutes les factures après auto-auth
    """

    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip("\"'")

    LOGIN = os.getenv("FREE_MOBILE_LOGIN", "12345678")
    PASSWORD = os.getenv("FREE_MOBILE_PASSWORD", "votre_mot_de_passe")
    GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "gmail.json")
    GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "gmail.json")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "factures_free")

    if LOGIN == "12345678" or PASSWORD == "votre_mot_de_passe":
        logger.error("Veuillez configurer vos identifiants dans le fichier .env")
        return

    downloader = FreeMobileInvoiceDownloader(
        auto_auth=True,
        login=LOGIN,
        password=PASSWORD,
        gmail_credentials_path=GMAIL_CREDENTIALS_PATH,
        gmail_token_path=GMAIL_TOKEN_PATH,
        output_dir=OUTPUT_DIR,
    )

    logger.info("Début du téléchargement des factures...")
    total, downloaded = await downloader.download_all_invoices()

    if downloaded > 0:
        logger.info(
            f"✅ {downloaded} factures téléchargées avec succès dans le dossier '{OUTPUT_DIR}'"
        )
    else:
        logger.warning("❌ Aucune facture n'a pu être téléchargée")


if __name__ == "__main__":
    asyncio.run(main())
