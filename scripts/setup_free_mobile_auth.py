#!/usr/bin/env python3
"""
Script d'installation pour l'authentification automatisée Free Mobile
"""

import os
import sys
import subprocess
import platform
import logging
import urllib.request
import zipfile

# Configuration du logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_python_version():
    """Vérifie la version de Python"""
    if sys.version_info < (3, 12):
        logger.error("Python 3.12 ou supérieur est requis")
        return False
    logger.info(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} détecté")
    return True


def install_chrome():
    """Installe Chrome/Chromium selon le système"""
    system = platform.system().lower()

    try:
        if system == "linux":
            # Détection de la distribution
            if os.path.exists("/etc/debian_version"):
                logger.info("Installation de Chromium sur Debian/Ubuntu...")
                subprocess.run(["sudo", "apt", "update"], check=True)
                subprocess.run(
                    ["sudo", "apt", "install", "-y", "chromium-browser"], check=True
                )
                logger.info("✅ Chromium installé")
            elif os.path.exists("/etc/redhat-release"):
                logger.info("Installation de Chromium sur RHEL/CentOS...")
                subprocess.run(["sudo", "yum", "install", "-y", "chromium"], check=True)
                logger.info("✅ Chromium installé")
            else:
                logger.warning(
                    "Distribution Linux non reconnue, veuillez installer Chrome/Chromium manuellement"
                )
                return False
        elif system == "darwin":
            logger.info(
                "Sur macOS, veuillez installer Chrome depuis https://www.google.com/chrome/"
            )
            return True
        elif system == "windows":
            logger.info(
                "Sur Windows, veuillez installer Chrome depuis https://www.google.com/chrome/"
            )
            return True
        else:
            logger.warning(f"Système {system} non supporté")
            return False

        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Erreur lors de l'installation de Chrome: {e}")
        return False


def install_chromedriver():
    """Installe ChromeDriver"""
    try:
        logger.info("Installation de ChromeDriver...")

        # Vérification si déjà installé
        result = subprocess.run(
            ["chromedriver", "--version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            logger.info("✅ ChromeDriver déjà installé")
            return True

        # Installation via apt (Ubuntu/Debian)
        try:
            subprocess.run(
                ["sudo", "apt", "install", "-y", "chromium-chromedriver"], check=True
            )
            logger.info("✅ ChromeDriver installé via apt")
            return True
        except subprocess.CalledProcessError:
            logger.warning(
                "Installation via apt échouée, tentative de téléchargement manuel..."
            )

        # Récupération de la dernière version
        with urllib.request.urlopen(
            "https://chromedriver.storage.googleapis.com/LATEST_RELEASE"
        ) as response:
            latest_version = response.read().decode().strip()

        # Téléchargement
        system = platform.system().lower()
        machine = platform.machine().lower()

        if system == "linux" and machine in ["x86_64", "amd64"]:
            arch = "linux64"
        elif system == "darwin":
            arch = "mac64"
        elif system == "windows":
            arch = "win32"
        else:
            logger.error(f"Architecture non supportée: {system} {machine}")
            return False

        url = f"https://chromedriver.storage.googleapis.com/{latest_version}/chromedriver_{arch}.zip"
        zip_path = "chromedriver.zip"

        logger.info(f"Téléchargement de ChromeDriver {latest_version}...")
        urllib.request.urlretrieve(url, zip_path)

        # Extraction
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(".")

        # Installation
        subprocess.run(["sudo", "mv", "chromedriver", "/usr/local/bin/"], check=True)
        subprocess.run(
            ["sudo", "chmod", "+x", "/usr/local/bin/chromedriver"], check=True
        )

        # Nettoyage
        os.remove(zip_path)

        logger.info("✅ ChromeDriver installé manuellement")
        return True

    except Exception as e:
        logger.error(f"Erreur lors de l'installation de ChromeDriver: {e}")
        return False


def check_gmail_credentials():
    """Vérifie la présence des credentials Gmail"""
    if os.path.exists("gmail.json"):
        logger.info("✅ Fichier gmail.json trouvé")
        return True
    else:
        logger.warning("❌ Fichier gmail.json non trouvé")
        logger.info(
            "Veuillez télécharger le fichier credentials.json depuis Google Cloud Console"
        )
        logger.info("et le renommer en gmail.json")
        return False


def create_config_template():
    """Crée un fichier de configuration template"""
    config_content = '''#!/usr/bin/env python3
"""
Configuration pour l'authentification Free Mobile
Renommez ce fichier en config.py et modifiez les valeurs
"""

# Configuration Free Mobile
FREE_MOBILE_LOGIN = "12345678"  # Votre identifiant Free Mobile (8 chiffres)
FREE_MOBILE_PASSWORD = "votre_mot_de_passe"

# Configuration Gmail
GMAIL_CREDENTIALS_PATH = "gmail.json"
GMAIL_TOKEN_PATH = "gmail.json"

# Configuration du téléchargement
OUTPUT_DIR = "factures_free"
HEADLESS_MODE = True  # False pour voir le navigateur
MAX_WAIT_TIME = 120  # Délai max d'attente pour le code email (secondes)
'''

    try:
        with open("config_template.py", "w") as f:
            f.write(config_content)
        logger.info("✅ Fichier config_template.py créé")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la création du template: {e}")
        return False


def run_tests():
    """Lance les tests de base"""
    try:
        logger.info("Lancement des tests de base...")

        # Test d'import
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        try:
            logger.info("✅ Import GmailManager réussi")
        except ImportError as e:
            logger.warning(f"⚠️ Import GmailManager échoué: {e}")

        try:
            logger.info("✅ Import FreeMobileAuthenticator réussi")
        except ImportError as e:
            logger.warning(f"⚠️ Import FreeMobileAuthenticator échoué: {e}")

        return True
    except Exception as e:
        logger.error(f"Erreur lors des tests: {e}")
        return False


def main():
    """Fonction principale d'installation"""
    logger.info("=== Installation de l'authentification Free Mobile ===")

    # Vérifications de base
    if not check_python_version():
        return False

    # Installation de Chrome
    if not install_chrome():
        logger.warning(
            "Installation de Chrome échouée, veuillez l'installer manuellement"
        )

    # Installation de ChromeDriver
    if not install_chromedriver():
        logger.warning(
            "Installation de ChromeDriver échouée, veuillez l'installer manuellement"
        )

    # Vérification des credentials Gmail
    check_gmail_credentials()

    # Création du template de configuration
    create_config_template()

    # Tests de base
    run_tests()

    logger.info("\n=== Installation terminée ===")
    logger.info("Prochaines étapes:")
    logger.info("1. Configurez vos credentials Gmail (gmail.json)")
    logger.info("2. Modifiez config_template.py avec vos identifiants")
    logger.info("3. Testez avec: python scripts/test_free_mobile_auth.py")
    logger.info("4. Lancez le téléchargement: python -m app.sources.free_mobile")

    return True


if __name__ == "__main__":
    main()
