#!/usr/bin/env python3
"""
Script pour télécharger les factures Free (Freebox)
Utilise Selenium pour l'authentification et la navigation
"""

import os
import re
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import requests
from html import unescape
from datetime import datetime

from app.sources.invoice import Invoice
from app.core.date_utils import parse_date_label_to_date

# Configuration du logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FreeInvoiceDownloader:
    def __init__(
        self,
        output_dir: str = "factures_free",
        login: Optional[str] = None,
        password: Optional[str] = None,
        headless: bool = True,
        timeout: int = 30,
    ):
        """
        Initialise le téléchargeur de factures Free

        Args:
            output_dir (str): Répertoire de sortie pour les factures
            login (str, optional): Identifiant Free pour auto-auth
            password (str, optional): Mot de passe Free pour auto-auth
            headless (bool): Mode headless pour le navigateur
            timeout (int): Timeout en secondes pour les attentes
        """
        self.base_url = "https://subscribe.free.fr"
        self.login_url = f"{self.base_url}/login"
        self.account_url = "https://adsl.free.fr"
        self.output_dir = output_dir
        self.login = login
        self.password = password
        self.timeout = timeout
        self.driver = None
        self.invoices_host = "https://adsl.free.fr"

        # Création du répertoire de sortie
        os.makedirs(self.output_dir, exist_ok=True)

        # Configuration du navigateur Chrome
        self.chrome_options = Options()
        if headless:
            self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        self.chrome_options.add_argument(f"--user-agent={self.user_agent}")

    def _init_driver(self):
        """Initialise le driver Selenium"""
        try:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.implicitly_wait(10)
            logger.info("Driver Chrome initialisé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du driver Chrome: {e}")
            raise

    def _wait_for_element(
        self, by: By, value: str, timeout: Optional[int] = None
    ) -> Any:
        """
        Attend qu'un élément soit présent sur la page

        Args:
            by: Méthode de localisation (By.ID, By.CSS_SELECTOR, etc.)
            value: Valeur de localisation
            timeout: Timeout personnalisé

        Returns:
            L'élément trouvé
        """
        wait_timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, wait_timeout)
        return wait.until(EC.presence_of_element_located((by, value)))

    def _wait_for_element_clickable(
        self, by: By, value: str, timeout: Optional[int] = None
    ) -> Any:
        """
        Attend qu'un élément soit cliquable

        Args:
            by: Méthode de localisation
            value: Valeur de localisation
            timeout: Timeout personnalisé

        Returns:
            L'élément cliquable
        """
        wait_timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, wait_timeout)
        return wait.until(EC.element_to_be_clickable((by, value)))

    def _requests_session_from_driver(self) -> "requests.Session":
        """
        Construit une session requests à partir des cookies du navigateur Selenium.
        """
        if not self.driver:
            raise RuntimeError("Driver Selenium non initialisé")
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        for cookie in self.driver.get_cookies():
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )
        return session

    def authenticate(self) -> bool:
        """
        Authentification avec Selenium

        Returns:
            bool: True si l'authentification réussit
        """
        if not self.login or not self.password:
            logger.error("Identifiants manquants pour l'authentification automatique")
            return False

        try:
            logger.info("Début de l'authentification...")

            # Initialisation du driver
            self._init_driver()

            # Navigation vers la page de connexion
            self.driver.get(self.login_url)
            logger.info(f"Navigation vers {self.login_url}")

            # Attente et saisie de l'identifiant
            logger.info("Saisie de l'identifiant...")
            id_field = self._wait_for_element(By.CSS_SELECTOR, "input[type='text']")
            id_field.clear()
            id_field.send_keys(self.login)

            # Saisie du mot de passe
            logger.info("Saisie du mot de passe...")
            password_field = self._wait_for_element(
                By.CSS_SELECTOR, "input[type='password']"
            )
            password_field.clear()
            password_field.send_keys(self.password)

            # Clic sur le bouton de connexion
            logger.info("Clic sur le bouton de connexion...")
            login_button = self._wait_for_element_clickable(
                By.CSS_SELECTOR, "button.login_button#ok"
            )
            login_button.click()

            # Attente de redirection vers l'espace abonné
            time.sleep(3)

            # Récupération de l'URL de redirection
            redirect_url = self.driver.current_url
            logger.info(f"URL de redirection: {redirect_url}")

            # Vérification de la connexion réussie
            if "login" not in redirect_url.lower():
                # Utilisation de l'URL de redirection comme account_url
                self.account_url = redirect_url
                logger.info("✅ Authentification réussie !")
                return True
            else:
                logger.error(
                    "❌ Authentification échouée - toujours sur la page de login"
                )
                return False

        except TimeoutException as e:
            logger.error(f"Timeout lors de l'authentification: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur lors de l'authentification: {e}")
            return False

    def check_authentication(self) -> bool:
        """
        Vérifie si l'authentification est valide

        Returns:
            bool: True si authentifié, False sinon
        """
        if not self.driver:
            return False

        try:
            # Navigation vers la page d'accueil
            self.driver.get(self.account_url)

            # Vérification si on est redirigé vers la page de login
            if "login" in self.driver.current_url.lower():
                logger.warning("Session non authentifiée ou expirée")
                return False

            # Vérification du contenu de la page
            page_source = self.driver.page_source
            if "Bienvenue" in page_source or "Espace Abonné" in page_source:
                logger.info("Session authentifiée valide")
                return True
            else:
                logger.warning("Session peut-être expirée")
                return False

        except Exception as e:
            logger.error(f"Erreur lors de la vérification d'authentification: {e}")
            return False

    def ensure_authentication(self) -> bool:
        """
        S'assure que l'authentification est valide, sinon tente l'authentification automatique

        Returns:
            bool: True si authentifié, False sinon
        """
        if self.check_authentication():
            return True

        logger.info("Tentative d'authentification automatique...")
        return self.authenticate()

    def get_page_content(self, url: str) -> Optional[str]:
        """
        Récupère le contenu d'une page avec Selenium

        Args:
            url (str): URL à récupérer

        Returns:
            str: Contenu HTML de la page ou None si erreur
        """
        try:
            if not self.driver:
                logger.error("Driver Selenium non initialisé")
                return None

            self.driver.get(url)
            return self.driver.page_source
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la page {url}: {e}")
            return None

    def navigate_to_all_invoices_page(self) -> bool:
        """
        Navigue vers la page "Voir toutes mes factures" en cliquant sur le lien

        Returns:
            bool: True si la navigation réussit, False sinon
        """
        try:
            # Vérification et authentification si nécessaire
            if not self.ensure_authentication():
                logger.error("Impossible de s'authentifier")
                return False

            logger.info(f"Navigation vers la page d'accueil: {self.account_url}")
            self.driver.get(self.account_url)
            time.sleep(2)

            # Recherche et clic sur le lien "Voir toutes mes factures"
            try:
                all_invoices_link = self._wait_for_element_clickable(
                    By.XPATH,
                    "//a[contains(text(), 'Voir toutes mes factures')]",
                    timeout=10,
                )
                logger.info("Lien 'Voir toutes mes factures' trouvé, clic...")
                all_invoices_link.click()
                time.sleep(3)  # Attente pour le chargement de la page
                logger.info("Navigation vers la page de toutes les factures réussie")
                return True
            except TimeoutException:
                logger.error("Lien 'Voir toutes mes factures' non trouvé")
                return False

        except Exception as e:
            logger.error(f"Erreur lors de la navigation vers la page des factures: {e}")
            return False

    def extract_invoice_info_from_list(self, invoice_element) -> Optional[Invoice]:
        """
        Extrait les informations d'une facture depuis la liste complète
        """
        try:
            # Extraction de tous les spans
            spans = invoice_element.find_all("span", class_="col")

            date_text = "Date inconnue"
            amount_text = "0,00€"

            if len(spans) >= 2:
                date_text = spans[1].get_text(strip=True)

            amount_element = invoice_element.find("span", class_="col last")
            if amount_element:
                amount_text = amount_element.get_text(strip=True)

            # Normalisation et extraction du montant en euros (float)
            amount_eur: Optional[float] = None
            if amount_text:
                try:
                    normalized = (
                        amount_text.replace("\xa0", " ")
                        .replace("€", "")
                        .replace("EUR", "")
                        .strip()
                    )
                    normalized = normalized.replace(" ", "")
                    normalized = normalized.replace(",", ".")
                    match = re.search(r"(\d+(?:\.\d{1,2})?)", normalized)
                    if match:
                        amount_eur = float(match.group(1))
                except Exception:
                    amount_eur = None

            # Extraction du lien de téléchargement
            download_link = None
            download_element = invoice_element.find("a", class_="btn_download")
            if download_element:
                raw_href = download_element.get("href")
                if raw_href:
                    raw_href = unescape(raw_href)
                    if raw_href.startswith("http"):
                        download_link = raw_href
                    elif raw_href.startswith("/"):
                        download_link = urljoin(self.invoices_host, raw_href)
                    else:
                        download_link = urljoin(self.invoices_host + "/", raw_href)

            # Extraction de l'ID de facture
            invoice_id = None
            if download_link:
                match = re.search(r"no_facture=(\d+)", download_link)
                if match:
                    invoice_id = match.group(1)

            return Invoice(
                date=date_text,
                invoice_id=invoice_id,
                amount_text=amount_text,
                amount_eur=amount_eur,
                download_url=download_link if download_link else None,
                view_url=None,
                source="Free",
            )

        except Exception as e:
            logger.error(
                f"Erreur lors de l'extraction des informations de facture: {e}"
            )
            return None

    def get_invoices_by_year(self, year: int) -> List[Invoice]:
        """
        Récupère toutes les factures d'une année spécifique
        """
        try:
            # Navigation vers la page de toutes les factures
            if not self.navigate_to_all_invoices_page():
                logger.error("Impossible de naviguer vers la page des factures")
                return []

            # Récupération du contenu de la page
            page_content = self.driver.page_source
            soup = BeautifulSoup(page_content, "html.parser")

            logger.info(f"Récupération des factures pour l'année {year}...")

            invoices: List[Invoice] = []

            # Tenter de cibler le conteneur principal des factures
            content_div = soup.find("div", id="content", class_="monabo mesfactures")
            li_candidates = []
            if content_div:
                li_candidates = content_div.find_all("li")
            if not li_candidates:
                # Fallback: chercher tous les <li> susceptibles de contenir des factures
                li_candidates = soup.find_all("li")

            for li in li_candidates:
                inv = self.extract_invoice_info_from_list(li)
                if not inv:
                    continue
                # Filtrer par année
                inv_dt = parse_date_label_to_date(inv.date or "")
                if inv_dt is not None:
                    if inv_dt.year == year:
                        invoices.append(inv)
                else:
                    # Fallback: si parsing impossible, filtrer par présence du texte de l'année
                    if str(year) in (inv.date or ""):
                        invoices.append(inv)

            logger.info(f"Total de {len(invoices)} factures trouvées pour {year}")
            return invoices

        except Exception as e:
            logger.error(f"Erreur inattendue: {e}")
            return []

    def download_invoice(self, invoice: Invoice) -> bool:
        """
        Télécharge une facture spécifique directement via HTTP en utilisant les cookies de session Selenium.
        """
        if not invoice or (not invoice.download_url and not invoice.invoice_id):
            logger.warning(
                f"Informations insuffisantes pour télécharger la facture {getattr(invoice, 'date', 'inconnue')}"
            )
            return False

        try:
            # Génération du nom de fichier
            filename = invoice.suggested_filename(prefix="Free")
            filepath = os.path.join(self.output_dir, filename)

            # Vérification si le fichier existe déjà
            if os.path.exists(filepath):
                logger.info(f"Fichier déjà existant: {filename}")
                return True

            logger.info(f"Téléchargement direct de la facture {invoice.date}...")

            # Déterminer l'URL de téléchargement
            href = invoice.download_url
            invoice_id = invoice.invoice_id
            if not href and invoice_id:
                try:
                    link_el = self._wait_for_element(
                        By.CSS_SELECTOR,
                        f"a[href*='no_facture={invoice_id}']",
                        timeout=5,
                    )
                    href = link_el.get_attribute("href")
                except Exception:
                    href = None

            if not href:
                logger.error(
                    f"URL de téléchargement introuvable pour la facture {invoice_id}"
                )
                return False

            # Normaliser l'URL (domaine adsl.free.fr + déséchappage)
            href = unescape(href)
            if href.startswith("http"):
                pass
            elif href.startswith("/"):
                href = urljoin(self.invoices_host, href)
            else:
                href = urljoin(self.invoices_host + "/", href)
            logger.info(f"URL de téléchargement: {href}")

            # Construire la session HTTP depuis Selenium
            session = self._requests_session_from_driver()

            # Lancer la requête HTTP
            response = session.get(
                href,
                stream=True,
                allow_redirects=True,
                headers={"Referer": self.driver.current_url},
                timeout=self.timeout,
            )

            if response.status_code != 200:
                logger.error(
                    f"Téléchargement direct échoué (status={response.status_code}) pour {invoice_id}"
                )
                return False

            # Écrire le contenu dans le fichier
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            logger.info(f"Fichier téléchargé: {filename}")
            return True

        except Exception as e:
            logger.error(
                f"Erreur lors du téléchargement direct de la facture {getattr(invoice, 'date', 'inconnue')}: {e}"
            )
            return False

    def download_invoices_from(self, from_date: str) -> tuple:
        """
        Télécharge toutes les factures à partir d'une date donnée (incluse).

        Args:
            from_date (str): Date de départ (formats supportés: 2024-01-01, 2024-01, 01/2024, "Janvier 2024")

        Returns:
            tuple: (total_candidats, total_téléchargés)
        """
        parsed_from = parse_date_label_to_date(from_date)
        if not parsed_from:
            logger.error(
                f"Date invalide: '{from_date}'. Exemples: 2024-01-01, 2024-01, 01/2024, 'Janvier 2024'"
            )
            return 0, 0

        # Récupérer les factures à partir de l'année de from_date jusqu'à l'année courante
        current_year = datetime.now().year
        invoices: List[Invoice] = []
        for y in range(parsed_from.year, current_year + 1):
            try:
                invs = self.get_invoices_by_year(y)
                invoices.extend(invs)
            except Exception:
                continue

        # Filtrer par date réelle
        filtered: List[Invoice] = []
        for inv in invoices:
            inv_dt = parse_date_label_to_date(inv.date or "")
            if inv_dt and inv_dt >= parsed_from:
                filtered.append(inv)

        downloaded = 0
        for inv in filtered:
            if self.download_invoice(inv):
                downloaded += 1

        logger.info(
            f"Téléchargement terminé: {downloaded}/{len(filtered)} factures téléchargées (>= {from_date})"
        )
        return len(filtered), downloaded

    def close(self):
        """
        Ferme proprement les ressources (session Selenium)
        """
        if self.driver:
            self.driver.quit()
            logger.info("Session Selenium fermée")


def main():
    """
    Exemple d'utilisation: téléchargement à partir d'une date
    """

    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip("\"'")

    LOGIN = os.getenv("FREE_LOGIN", "fbx12345678")
    PASSWORD = os.getenv("FREE_PASSWORD", "votre_mot_de_passe")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "factures_free")
    FROM_DATE = os.getenv("FROM_DATE", "").strip()
    HEADLESS = os.getenv("HEADLESS_MODE", "true").lower() == "true"

    if LOGIN == "fbx12345678" or PASSWORD == "votre_mot_de_passe":
        logger.error("Veuillez configurer vos identifiants dans le fichier .env")
        return

    downloader = FreeInvoiceDownloader(
        login=LOGIN,
        password=PASSWORD,
        output_dir=OUTPUT_DIR,
        headless=HEADLESS,
    )

    if not FROM_DATE:
        logger.error("Veuillez définir FROM_DATE (ex: 2024-01-01)")
        downloader.close()
        return
    total, downloaded = downloader.download_invoices_from(FROM_DATE)
    if downloaded == 0:
        logger.warning(
            f"❌ Aucune facture n'a pu être téléchargée à partir de {FROM_DATE}"
        )

    downloader.close()


if __name__ == "__main__":
    main()
