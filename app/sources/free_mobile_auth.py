#!/usr/bin/env python3
"""
Module d'authentification automatisée pour Free Mobile
Utilise Selenium pour l'authentification et Gmail Manager pour récupérer le code de sécurité
"""

import os
import asyncio
from pathlib import Path
import re
import time
import logging
from typing import Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from app.sources.gmail_manager import GmailManager

# Configuration du logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FreeMobileAuthenticator:
    """
    Classe pour gérer l'authentification automatisée sur Free Mobile
    """

    def __init__(
        self,
        gmail_credentials_path: str = "gmail.json",
        gmail_token_path: str = "gmail.json",
        headless: bool = False,
        timeout: int = 30,
    ):
        """
        Initialise l'authentificateur Free Mobile

        Args:
            gmail_credentials_path (str): Chemin vers le fichier credentials.json Gmail
            gmail_token_path (str): Chemin vers le fichier token.json Gmail
            headless (bool): Mode headless pour le navigateur
            timeout (int): Timeout en secondes pour les attentes
        """
        self.base_url = "https://mobile.free.fr"
        self.login_url = f"{self.base_url}/account/v2"
        self.timeout = timeout
        self.driver = None
        self.gmail_manager = None

        # Configuration du navigateur Chrome
        self.chrome_options = Options()
        if headless:
            self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )

        # Initialisation du gestionnaire Gmail
        try:
            self.gmail_manager = GmailManager(
                credentials_path=gmail_credentials_path, token_path=gmail_token_path
            )
            logger.info("Gestionnaire Gmail initialisé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du gestionnaire Gmail: {e}")
            raise

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

    def login_step1(self, login: str, password: str) -> bool:
        """
        Première étape de connexion : saisie du login et mot de passe

        Args:
            login (str): Identifiant Free Mobile (8 chiffres)
            password (str): Mot de passe

        Returns:
            bool: True si la première étape réussit
        """
        try:
            logger.info("Début de la première étape d'authentification...")

            # Navigation vers la page de connexion
            self.driver.get(self.login_url)
            logger.info(f"Navigation vers {self.login_url}")

            # Attente et saisie de l'identifiant
            logger.info("Saisie de l'identifiant...")
            id_field = self._wait_for_element(By.CSS_SELECTOR, "input[type='text']")
            id_field.clear()
            id_field.send_keys(login)

            # Saisie du mot de passe
            logger.info("Saisie du mot de passe...")
            password_field = self._wait_for_element(
                By.CSS_SELECTOR, "input[type='password']"
            )
            password_field.clear()
            password_field.send_keys(password)

            # Clic sur le bouton de connexion
            logger.info("Clic sur le bouton de connexion...")
            login_button = self._wait_for_element_clickable(
                By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"
            )
            login_button.click()

            # Attente de la page de vérification 2FA
            logger.info("Attente de la page de vérification 2FA...")
            self._wait_for_element(By.XPATH, "//h1[contains(text(), 'Plus qu')]")

            logger.info("Première étape d'authentification réussie")
            return True

        except TimeoutException as e:
            logger.error(f"Timeout lors de la première étape: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur lors de la première étape: {e}")
            return False

    def request_email_code(self) -> Optional[float]:
        """
        Demande l'envoi du code par email

        Returns:
            float: Timestamp de la demande ou None si échec
        """
        try:
            logger.info("Demande d'envoi du code par email...")

            # Recherche du bouton "envoi de code par email" avec l'ID spécifique
            email_button = self._wait_for_element_clickable(
                By.CSS_SELECTOR, "button#auth-2FA-retry"
            )
            email_button.click()

            # Attente de confirmation
            time.sleep(2)
            request_time = time.time()
            logger.info(f"Demande de code par email envoyée à {request_time}")
            return request_time

        except TimeoutException:
            logger.warning(
                "Bouton 'envoi de code par email' non trouvé, tentative de recherche alternative..."
            )
            try:
                # Recherche alternative avec le texte du bouton
                email_button = self.driver.find_element(
                    By.XPATH,
                    "//button[contains(text(), 'envoi de code par email')]",
                )
                email_button.click()
                time.sleep(2)
                request_time = time.time()
                logger.info(
                    f"Demande de code par email envoyée (recherche alternative) à {request_time}"
                )
                return request_time
            except NoSuchElementException:
                logger.error(
                    "Impossible de trouver le bouton pour demander le code par email"
                )
                return None
        except Exception as e:
            logger.error(f"Erreur lors de la demande de code par email: {e}")
            return None

    async def get_security_code_from_gmail(
        self, max_wait_time: int = 300, request_time: Optional[float] = None
    ) -> Optional[str]:
        """
        Récupère le code de sécurité depuis Gmail de manière asynchrone

        Args:
            max_wait_time (int): Temps maximum d'attente en secondes
            request_time (float): Timestamp de la demande du code (si None, utilise le temps actuel)

        Returns:
            str: Le code de sécurité ou None si non trouvé
        """
        try:
            # Utilise le temps de demande fourni ou le temps actuel
            if request_time is None:
                request_time = time.time()

            logger.info(
                f"Recherche du code de sécurité dans Gmail (attente max: {max_wait_time}s, depuis {request_time})..."
            )

            start_time = time.time()
            while time.time() - start_time < max_wait_time:
                # Recherche des emails avec les critères spécifiés
                query = "subject:'Validez l'accès à votre Espace Abonné' from:freemobile@free-mobile.fr"
                emails = self.gmail_manager.search_emails(query, max_results=10)

                if emails:
                    logger.info(f"Emails trouvés: {len(emails)}")

                    # Filtrage des emails par date d'envoi (après la demande du code)
                    filtered_emails = []
                    for email in emails:
                        email_time = int(email.get("internalDate", "0")) / 1000
                        if email_time >= request_time:
                            filtered_emails.append(email)
                            logger.info(
                                f"Email postérieur à la demande trouvé: {email.get('subject', 'N/A')} - {email_time}"
                            )

                    # Traitement des emails filtrés
                    for email in filtered_emails:
                        body = email.get("body", "")
                        if body:
                            # Extraction du code avec regex
                            code_match = re.search(r"<strong>(\d{6})</strong>", body)
                            if code_match:
                                code = code_match.group(1)
                                logger.info(f"Code de sécurité trouvé: {code}")
                                return code
                else:
                    logger.info("Aucun email trouvé")

                logger.info("Code non trouvé, nouvelle tentative dans 10 secondes...")
                await asyncio.sleep(10)

            logger.error("Code de sécurité non trouvé dans le délai imparti")
            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du code depuis Gmail: {e}")
            return None

    def enter_security_code(self, code: str) -> bool:
        """
        Saisit le code de sécurité caractère par caractère

        Args:
            code (str): Code de sécurité à saisir (6 chiffres)

        Returns:
            bool: True si la saisie réussit
        """
        try:
            logger.info(f"Saisie du code de sécurité: {code}")

            # Recherche des champs de saisie du code avec le sélecteur spécifique
            code_inputs = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type='number'][inputmode='numeric'][pattern='[0-9]']",
            )

            if len(code_inputs) >= 6:
                logger.info(f"Trouvé {len(code_inputs)} champs de saisie")

                # Saisie caractère par caractère avec focus et délai
                for i, digit in enumerate(code[:6]):
                    try:
                        # Focus sur le champ
                        code_inputs[i].click()
                        time.sleep(0.2)

                        # Nettoyage et saisie
                        code_inputs[i].clear()
                        time.sleep(0.1)
                        code_inputs[i].send_keys(digit)
                        time.sleep(0.2)

                        logger.info(f"Chiffre {i + 1}: {digit}")
                    except Exception as e:
                        logger.error(
                            f"Erreur lors de la saisie du chiffre {i + 1}: {e}"
                        )
                        return False
            else:
                logger.warning(
                    f"Nombre insuffisant de champs trouvés: {len(code_inputs)}"
                )
                # Recherche alternative avec un sélecteur plus générique
                code_inputs = self.driver.find_elements(
                    By.CSS_SELECTOR, "input[type='number']"
                )

                if len(code_inputs) >= 6:
                    logger.info("Utilisation du sélecteur alternatif")
                    for i, digit in enumerate(code[:6]):
                        code_inputs[i].clear()
                        code_inputs[i].send_keys(digit)
                        time.sleep(0.2)
                else:
                    logger.error("Impossible de trouver les champs de saisie du code")
                    return False

            # Clic sur le bouton "Valider"
            logger.info("Clic sur le bouton Valider...")
            validate_button = self._wait_for_element_clickable(
                By.ID, "auth-2FA-validate"
            )
            validate_button.click()

            # Attente de redirection vers l'espace abonné
            time.sleep(3)

            # Vérification de la connexion réussie
            if "account/v2" in self.driver.current_url:
                logger.info("Authentification réussie !")
                return True
            else:
                logger.warning(
                    "Authentification peut-être échouée, vérification de l'URL..."
                )
                return False

        except TimeoutException as e:
            logger.error(f"Timeout lors de la saisie du code: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur lors de la saisie du code: {e}")
            return False

    def get_cookies(self) -> Dict[str, str]:
        """
        Récupère les cookies de session après authentification

        Returns:
            Dict[str, str]: Dictionnaire des cookies
        """
        try:
            cookies = {}
            for cookie in self.driver.get_cookies():
                cookies[cookie["name"]] = cookie["value"]

            logger.info(f"Cookies récupérés: {list(cookies.keys())}")
            return cookies
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des cookies: {e}")
            return {}

    async def authenticate(
        self, login: str, password: str, max_wait_time: int = 120
    ) -> Optional[Dict[str, str]]:
        """
        Processus complet d'authentification (version asynchrone)

        Args:
            login (str): Identifiant Free Mobile
            password (str): Mot de passe
            max_wait_time (int): Temps maximum d'attente pour le code email

        Returns:
            Dict[str, str]: Cookies de session ou None si échec
        """
        try:
            logger.info("Début du processus d'authentification automatisée...")

            # Initialisation du driver
            self._init_driver()

            # Première étape : login/password
            if not self.login_step1(login, password):
                logger.error("Échec de la première étape d'authentification")
                return None

            # Demande du code par email
            request_time = self.request_email_code()
            if request_time is None:
                logger.error("Échec de la demande de code par email")
                return None

            # Récupération du code depuis Gmail (avec le timestamp de la demande)
            security_code = await self.get_security_code_from_gmail(
                max_wait_time, request_time
            )
            if not security_code:
                logger.error("Impossible de récupérer le code de sécurité")
                return None

            # Saisie du code de sécurité
            if not self.enter_security_code(security_code):
                logger.error("Échec de la saisie du code de sécurité")
                return None

            # Récupération des cookies
            cookies = self.get_cookies()
            if not cookies:
                logger.error("Aucun cookie récupéré")
                return None

            logger.info("Authentification complète réussie !")
            return cookies

        except Exception as e:
            logger.error(f"Erreur lors du processus d'authentification: {e}")
            return None
        finally:
            # Fermeture du navigateur
            if self.driver:
                self.driver.quit()
                logger.info("Navigateur fermé")

    def close(self):
        """Ferme le navigateur"""
        if self.driver:
            self.driver.quit()
            logger.info("Navigateur fermé")


async def main():
    """
    Exemple d'utilisation de l'authentificateur Free Mobile (version asynchrone)
    """

    # Chargement des variables d'environnement depuis .env
    def load_env_file():
        """Charge les variables d'environnement depuis le fichier .env"""

        env_path = Path(__file__).parent.parent.parent / ".env"

        if env_path.exists():
            logger.info(f"Chargement des variables depuis {env_path}")
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        # Nettoyage complet des valeurs
                        key = key.strip()
                        value = value.strip().strip("\"'")
                        # Suppression des caractères invisibles (BOM, espaces, etc.)
                        value = value.encode("ascii", "ignore").decode("ascii").strip()
                        os.environ[key] = value
            logger.info("✅ Variables d'environnement chargées")
        else:
            logger.warning(f"Fichier .env non trouvé: {env_path}")

    # Chargement des variables d'environnement
    load_env_file()

    # Configuration pour l'authentification automatisée depuis .env
    LOGIN = os.getenv("FREE_MOBILE_LOGIN", "12345678")
    PASSWORD = os.getenv("FREE_MOBILE_PASSWORD", "votre_mot_de_passe")

    # Nettoyage des identifiants
    def clean_credentials(credential):
        """Nettoie les identifiants des caractères invisibles"""
        if credential:
            # Suppression des caractères invisibles et espaces
            cleaned = credential.strip()
            # Suppression des caractères non-ASCII
            cleaned = cleaned.encode("ascii", "ignore").decode("ascii").strip()
            return cleaned
        return credential

    LOGIN = clean_credentials(LOGIN)
    PASSWORD = clean_credentials(PASSWORD)

    try:
        # Création de l'authentificateur
        authenticator = FreeMobileAuthenticator(
            headless=False
        )  # False pour voir le navigateur

        # Authentification
        cookies = await authenticator.authenticate(LOGIN, PASSWORD)

        if cookies:
            logger.info("✅ Authentification réussie !")
            logger.info("Cookies récupérés:")
            for name, value in cookies.items():
                logger.info(f"  {name}: {value[:20]}...")
        else:
            logger.error("❌ Échec de l'authentification")

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution: {e}")


if __name__ == "__main__":
    asyncio.run(main())
