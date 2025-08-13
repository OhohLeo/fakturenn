#!/usr/bin/env python3
"""
Téléchargement des factures Free Mobile (flux synchronisé)
- Authentification automatisée intégrée (Selenium + code 2FA reçu par Gmail)
- Récupération et téléchargement via requests en réutilisant les cookies de session
- Structure inspirée de app/sources/free.py
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from app.sources.gmail_manager import GmailManager
from app.sources.invoice import Invoice
from app.core.date_utils import parse_date_label_to_date


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
        login: Optional[str] = None,
        password: Optional[str] = None,
        gmail_credentials_path: str = "gmail.json",
        gmail_token_path: str = "gmail.json",
        headless: bool = True,
        timeout: int = 30,
    ):
        """
        Initialise le téléchargeur de factures Free Mobile

        Args:
            session_id (str, optional): ACCOUNT_SESSID cookie
            user_token (str, optional): X_USER_TOKEN cookie
            selfcare_token (str, optional): SELFCARE_TOKEN cookie
            output_dir (str): Répertoire de sortie pour les factures
            login (str, optional): Identifiant Free Mobile (8 chiffres)
            password (str, optional): Mot de passe Free Mobile
            gmail_credentials_path (str): Chemin vers credentials.json Gmail
            gmail_token_path (str): Chemin vers token.json Gmail
            headless (bool): Mode headless pour Selenium
            timeout (int): Timeout d'attente des éléments Selenium (s)
        """
        self.base_url = "https://mobile.free.fr"
        self.account_url = f"{self.base_url}/account/v2"
        self.output_dir = output_dir
        self.login = login
        self.password = password
        self.gmail_credentials_path = gmail_credentials_path
        self.gmail_token_path = gmail_token_path
        self.timeout = timeout
        self.driver: Optional[webdriver.Chrome] = None
        self.gmail_manager: Optional[GmailManager] = None

        os.makedirs(self.output_dir, exist_ok=True)

        # Session HTTP pour le scraping et les téléchargements
        self.user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
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

        # Cookies manuels éventuels
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

        # Préparation des options Selenium
        self.chrome_options = Options()
        if headless:
            self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument(f"--user-agent={self.user_agent}")

        # Initialisation du gestionnaire Gmail (meilleure tentative)
        try:
            self.gmail_manager = GmailManager(
                credentials_path=self.gmail_credentials_path,
                token_path=self.gmail_token_path,
            )
            logger.info("Gestionnaire Gmail initialisé")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du gestionnaire Gmail: {e}")
            # Continuer: l'utilisateur peut avoir fourni des cookies

    # ======== Selenium helpers ========
    def _init_driver(self):
        try:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.implicitly_wait(10)
            logger.info("Driver Chrome initialisé")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du driver Chrome: {e}")
            raise

    def _wait_for_element(self, by: By, value: str, timeout: Optional[int] = None):
        wait_timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, wait_timeout)
        return wait.until(EC.presence_of_element_located((by, value)))

    def _wait_for_element_clickable(
        self, by: By, value: str, timeout: Optional[int] = None
    ):
        wait_timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, wait_timeout)
        return wait.until(EC.element_to_be_clickable((by, value)))

    # ======== Authentification (Selenium + Gmail) ========
    def _login_step1(self, login: str, password: str) -> bool:
        try:
            logger.info("Première étape d'authentification...")
            self.driver.get(self.account_url)

            id_field = self._wait_for_element(By.CSS_SELECTOR, "input[type='text']")
            id_field.clear()
            id_field.send_keys(login)

            password_field = self._wait_for_element(
                By.CSS_SELECTOR, "input[type='password']"
            )
            password_field.clear()
            password_field.send_keys(password)

            login_button = self._wait_for_element_clickable(
                By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"
            )
            login_button.click()

            # Attente de la page 2FA
            self._wait_for_element(By.XPATH, "//h1[contains(text(), 'Plus qu')]")
            logger.info("Étape de connexion (login/mot de passe) réussie")
            return True
        except TimeoutException as e:
            logger.error(f"Timeout lors de la première étape: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur lors de la première étape: {e}")
            return False

    def _request_email_code(self) -> Optional[float]:
        try:
            logger.info("Demande d'envoi du code par email...")
            email_button = self._wait_for_element_clickable(
                By.CSS_SELECTOR, "button#auth-2FA-retry"
            )
            email_button.click()
            time.sleep(2)
            ts = time.time()
            logger.info(f"Demande de code effectuée à {ts}")
            return ts
        except TimeoutException:
            logger.warning("Bouton 2FA par email non trouvé, recherche alternative...")
            try:
                email_button = self.driver.find_element(
                    By.XPATH, "//button[contains(text(), 'envoi de code par email')]"
                )
                email_button.click()
                time.sleep(2)
                ts = time.time()
                logger.info(f"Demande de code (fallback) à {ts}")
                return ts
            except NoSuchElementException:
                logger.error(
                    "Impossible de trouver le bouton pour demander le code par email"
                )
                return None
        except Exception as e:
            logger.error(f"Erreur lors de la demande de code: {e}")
            return None

    def _get_security_code_from_gmail(
        self, max_wait_time: int, request_time: float
    ) -> Optional[str]:
        try:
            if not self.gmail_manager:
                logger.error("Gestionnaire Gmail non initialisé")
                return None

            logger.info(
                f"Recherche du code de sécurité (attente max {max_wait_time}s)..."
            )
            start = time.time()
            while time.time() - start < max_wait_time:
                query = "subject:'Validez l'accès à votre Espace Abonné' from:freemobile@free-mobile.fr"
                emails = self.gmail_manager.search_emails(query, max_results=10)
                if emails:
                    filtered = []
                    for email in emails:
                        email_time = int(email.get("internalDate", "0")) / 1000
                        if email_time >= request_time:
                            filtered.append(email)
                    for email in filtered:
                        body = email.get("body", "")
                        if body:
                            match = re.search(r"<strong>(\d{6})</strong>", body)
                            if match:
                                code = match.group(1)
                                logger.info(f"Code 2FA trouvé: {code}")
                                return code
                logger.info("Code non trouvé, nouvelle tentative dans 10s...")
                time.sleep(10)
            logger.error("Code de sécurité non reçu dans le délai imparti")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du code Gmail: {e}")
            return None

    def _enter_security_code(self, code: str) -> bool:
        try:
            logger.info("Saisie du code de sécurité...")
            inputs = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type='number'][inputmode='numeric'][pattern='[0-9]']",
            )
            if len(inputs) < 6:
                inputs = self.driver.find_elements(
                    By.CSS_SELECTOR, "input[type='number']"
                )
            if len(inputs) < 6:
                logger.error("Champs de saisie du code non trouvés")
                return False

            for i, digit in enumerate(code[:6]):
                try:
                    inputs[i].click()
                    time.sleep(0.2)
                    inputs[i].clear()
                    time.sleep(0.1)
                    inputs[i].send_keys(digit)
                    time.sleep(0.2)
                except Exception as e:
                    logger.error(f"Erreur lors de la saisie du chiffre {i + 1}: {e}")
                    return False

            validate_button = self._wait_for_element_clickable(
                By.ID, "auth-2FA-validate"
            )
            validate_button.click()
            time.sleep(3)

            if "account/v2" in self.driver.current_url:
                logger.info("Authentification validée")
                return True
            logger.warning("Authentification peut-être échouée, URL inattendue")
            return False
        except TimeoutException as e:
            logger.error(f"Timeout lors de la validation du code: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur lors de la saisie du code: {e}")
            return False

    def _get_driver_cookies(self) -> Dict[str, str]:
        try:
            cookies: Dict[str, str] = {}
            for cookie in self.driver.get_cookies():
                cookies[cookie["name"]] = cookie["value"]
            logger.info(f"Cookies récupérés: {list(cookies.keys())}")
            return cookies
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des cookies: {e}")
            return {}

    def authenticate(self, max_wait_time: int = 180) -> bool:
        """
        Processus complet d'authentification:
        - Ouverture Selenium, login/mdp
        - Demande du code par email
        - Lecture du code Gmail
        - Validation et récupération des cookies
        - Application des cookies à la session requests
        """
        if not (self.login and self.password):
            logger.error(
                "Identifiants Free Mobile manquants pour l'authentification automatique"
            )
            return False

        try:
            if not self.gmail_manager:
                self.gmail_manager = GmailManager(
                    credentials_path=self.gmail_credentials_path,
                    token_path=self.gmail_token_path,
                )

            self._init_driver()

            if not self._login_step1(self.login, self.password):
                return False

            request_time = self._request_email_code()
            if request_time is None:
                return False

            code = self._get_security_code_from_gmail(
                max_wait_time=max_wait_time, request_time=request_time
            )
            if not code:
                return False

            if not self._enter_security_code(code):
                return False

            cookies = self._get_driver_cookies()
            if not cookies:
                return False

            # Application des cookies dans requests
            for name, value in cookies.items():
                self.session.cookies.set(name, value, domain="mobile.free.fr")

            logger.info("✅ Authentification automatisée réussie")
            return True
        except Exception as e:
            logger.error(f"Erreur lors du processus d'authentification: {e}")
            return False
        finally:
            # Ne pas fermer le navigateur ici pour permettre des interactions ultérieures
            pass

    # ======== Vérification de session ========
    def check_authentication(self) -> bool:
        try:
            response = self.session.get(
                self.account_url, allow_redirects=True, timeout=self.timeout
            )
            if "login" in response.url.lower() or "connexion" in response.url.lower():
                logger.warning(
                    "Session non authentifiée ou expirée (redirigé vers login)"
                )
                return False
            if any(token in response.text for token in ["Bienvenue", "Espace Abonné"]):
                logger.info("Session authentifiée valide")
                return True
            logger.warning("Session peut-être expirée")
            return False
        except Exception as e:
            logger.error(f"Erreur lors de la vérification d'authentification: {e}")
            return False

    def ensure_authentication(self) -> bool:
        if self.check_authentication():
            return True
        logger.info("Tentative d'authentification automatique...")
        return self.authenticate()

    def _ensure_driver_authenticated(self) -> bool:
        """S'assure que le driver Selenium est initialisé et authentifié en réinjectant les cookies de la session HTTP si nécessaire."""
        try:
            if not self.driver:
                self._init_driver()
                # Ouvrir le domaine pour pouvoir poser des cookies
                self.driver.get(self.account_url)
                time.sleep(1)
                # Injecter les cookies connus de la session requests
                for cookie in self.session.cookies:
                    try:
                        if cookie.domain and "mobile.free.fr" not in cookie.domain:
                            continue
                        self.driver.add_cookie(
                            {
                                "name": cookie.name,
                                "value": cookie.value,
                                "path": cookie.path or "/",
                            }
                        )
                    except Exception:
                        continue
            # Naviguer vers la page compte avec cookies en place
            self.driver.get(self.account_url)
            time.sleep(2)
            # Si toujours redirigé vers un login, relancer l'authentification complète
            if (
                "login" in self.driver.current_url.lower()
                or "connexion" in self.driver.current_url.lower()
            ):
                logger.info(
                    "Cookies Selenium invalides, tentative d'authentification complète..."
                )
                if not self.authenticate():
                    return False
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la préparation du driver authentifié: {e}")
            return False

    # ======== Parsing et téléchargement ========
    def _parse_amount_text(self, amount_text: Optional[str]) -> Optional[float]:
        if not amount_text:
            return None
        txt = amount_text.strip()
        txt = txt.replace("\xa0", " ").replace("€", "").replace(" ", "")
        txt = txt.replace(",", ".")
        try:
            return float(re.findall(r"[-+]?[0-9]*\.?[0-9]+", txt)[0])
        except Exception:
            return None

    def extract_invoice_info(self, invoice_element) -> Optional[Invoice]:
        try:
            # Date
            date_element = invoice_element.find("h3", class_="font-semibold")
            date_text = (
                date_element.get_text(strip=True) if date_element else "Date inconnue"
            )

            # Montant
            amount_element = invoice_element.find("span")
            amount_text = (
                amount_element.get_text(strip=True) if amount_element else "0,00€"
            )
            amount_eur = self._parse_amount_text(amount_text)

            # Lien de téléchargement
            download_element = invoice_element.find(
                "a", href=re.compile(r"/account/v2/api/SI/invoice/\d+\?display=1")
            )
            download_link = download_element.get("href") if download_element else None

            # Lien de visualisation
            view_element = invoice_element.find(
                "a", href=re.compile(r"/account/v2/api/SI/invoice/\d+$")
            )
            view_link = view_element.get("href") if view_element else None

            # ID
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

    def get_invoices_list(self, from_date: Optional[str] = None) -> List[Invoice]:
        try:
            # S'assurer de l'authentification (cookies pour HTTP) puis disposer d'un driver prêt
            if not self.ensure_authentication():
                logger.error("Impossible de s'authentifier")
                return []
            if not self._ensure_driver_authenticated():
                logger.error("Impossible de préparer un driver authentifié")
                return []

            logger.info(
                "Navigation vers la page des factures (onglet 'Mes factures')..."
            )
            # Cliquer sur l'onglet "Mes factures"
            try:
                tab_button = self._wait_for_element_clickable(
                    By.XPATH,
                    "//button[@role='tab' and @aria-controls='invoices' and contains(normalize-space(.), 'Mes factures')]",
                    timeout=10,
                )
                tab_button.click()
                time.sleep(1.5)
            except TimeoutException:
                # Fallback via texte exact
                try:
                    tab_button = self._wait_for_element_clickable(
                        By.XPATH,
                        "//button[normalize-space(text())='Mes factures']",
                        timeout=5,
                    )
                    tab_button.click()
                    time.sleep(1.5)
                except Exception:
                    logger.warning("Bouton 'Mes factures' introuvable ou déjà actif")

            # Cliquer sur "Voir plus" jusqu'à disparition
            logger.info("Expansion de la liste des factures via 'Voir plus'...")
            while True:
                try:
                    voir_plus_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable(
                            (
                                By.XPATH,
                                "//button[.//span[normalize-space(text())='Voir plus']]",
                            )
                        )
                    )
                    # Vérifier la visibilité réelle
                    if voir_plus_btn.is_displayed():
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});",
                            voir_plus_btn,
                        )
                        time.sleep(0.3)
                        voir_plus_btn.click()
                        time.sleep(
                            1.2
                        )  # Laisser le temps de charger de nouveaux éléments
                        continue
                except TimeoutException:
                    # Plus de bouton visible/clickable
                    break
                except Exception as e:
                    logger.debug(f"Interruption du clic sur 'Voir plus': {e}")
                    break

            # Récupérer le HTML complet après expansion
            page_html = self.driver.page_source
            soup = BeautifulSoup(page_html, "html.parser")

            # Recherche des éléments de facture
            invoice_elements = soup.find_all(
                "li", class_=re.compile(r"flex flex-col.*border")
            )

            invoices: List[Invoice] = []
            for element in invoice_elements:
                invoice = self.extract_invoice_info(element)
                if invoice:
                    invoices.append(invoice)
                    logger.info(
                        f"Facture trouvée: {invoice.date} - {invoice.amount_text}"
                    )

            # Filtrage par date si demandé
            if from_date:
                parsed = parse_date_label_to_date(from_date)
                if parsed:
                    invoices = [
                        inv
                        for inv in invoices
                        if parse_date_label_to_date(inv.date or "")
                        and parse_date_label_to_date(inv.date or "") >= parsed
                    ]

            logger.info(f"Total de {len(invoices)} factures trouvées")
            return invoices
        except requests.RequestException as e:
            logger.error(f"Erreur lors de la récupération de la page: {e}")
            return []
        except Exception as e:
            logger.error(f"Erreur inattendue: {e}")
            return []

    def download_invoice(
        self, invoice: Invoice, from_date: Optional[str] = None
    ) -> bool:
        # Si un from_date est fourni, ne télécharge que si la facture est >= from_date
        if from_date:
            parsed = parse_date_label_to_date(from_date)
            inv_dt = parse_date_label_to_date(getattr(invoice, "date", ""))
            if parsed and inv_dt and inv_dt < parsed:
                logger.info(f"Ignorée (date < from): {invoice.date} < {from_date}")
                return False

        if not invoice or not invoice.download_url:
            logger.warning(
                f"Pas d'URL de téléchargement pour la facture {getattr(invoice, 'date', 'inconnue')}"
            )
            return False
        try:
            filename = invoice.suggested_filename(prefix="Free_Mobile")
            filepath = os.path.join(self.output_dir, filename)
            if os.path.exists(filepath):
                logger.info(f"Fichier déjà existant: {filename}")
                return True

            logger.info(f"Téléchargement de la facture {invoice.date}...")
            response = self.session.get(invoice.download_url, timeout=self.timeout)
            response.raise_for_status()
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

    def download_all_invoices(self) -> tuple:
        invoices = self.get_invoices_list()
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

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Navigateur fermé")


def main():
    """
    Exemple d'utilisation synchronisée: télécharge toutes les factures après authentification automatique
    """
    # Chargement .env
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
    HEADLESS = os.getenv("HEADLESS_MODE", "true").lower() == "true"

    if LOGIN == "12345678" or PASSWORD == "votre_mot_de_passe":
        logger.error("Veuillez configurer vos identifiants dans le fichier .env")
        return

    downloader = FreeMobileInvoiceDownloader(
        login=LOGIN,
        password=PASSWORD,
        gmail_credentials_path=GMAIL_CREDENTIALS_PATH,
        gmail_token_path=GMAIL_TOKEN_PATH,
        output_dir=OUTPUT_DIR,
        headless=HEADLESS,
    )

    try:
        logger.info("Début du téléchargement des factures...")
        total, downloaded = downloader.download_all_invoices()
        if downloaded > 0:
            logger.info(
                f"✅ {downloaded} factures téléchargées avec succès dans le dossier '{OUTPUT_DIR}'"
            )
        else:
            logger.warning("❌ Aucune facture n'a pu être téléchargée")
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
    finally:
        downloader.close()


if __name__ == "__main__":
    main()
