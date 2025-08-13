#!/usr/bin/env python3
"""
Librairie pour la gestion des emails Gmail
Fonctionnalités: lecture, attribution de libellés, marquage comme lu
"""

import os
import base64
import logging
from typing import List, Dict, Optional, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configuration du logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Scopes Gmail nécessaires
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]


class GmailManager:
    """
    Classe pour gérer les emails Gmail avec lecture, libellés et marquage
    """

    def __init__(
        self, credentials_path: str = "gmail.json", token_path: str = "gmail.json"
    ):
        """
        Initialise le gestionnaire Gmail

        Args:
            credentials_path (str): Chemin vers le fichier credentials.json
            token_path (str): Chemin vers le fichier token.json
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authentification avec l'API Gmail"""
        creds = None

        # Vérification du token existant
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
                logger.info("Token d'authentification chargé depuis le fichier")
            except Exception as e:
                logger.warning(f"Erreur lors du chargement du token: {e}")

        # Si pas de token valide, authentification OAuth2
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Token rafraîchi avec succès")
                except Exception as e:
                    logger.error(f"Erreur lors du rafraîchissement du token: {e}")
                    creds = None

            if not creds:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Fichier credentials.json non trouvé: {self.credentials_path}\n"
                        "Veuillez télécharger le fichier depuis Google Cloud Console"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
                logger.info("Authentification OAuth2 réussie")

            # Sauvegarde du token
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())
            logger.info(f"Token sauvegardé dans {self.token_path}")

        # Création du service Gmail
        try:
            self.service = build("gmail", "v1", credentials=creds)
            logger.info("Service Gmail initialisé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du service Gmail: {e}")
            raise

    def get_labels(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des libellés disponibles

        Returns:
            List[Dict]: Liste des libellés avec leurs informations
        """
        try:
            results = self.service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])

            logger.info(f"Récupération de {len(labels)} libellés")
            return labels

        except HttpError as error:
            logger.error(f"Erreur lors de la récupération des libellés: {error}")
            return []

    def create_label(
        self,
        name: str,
        label_list_visibility: str = "labelShow",
        message_list_visibility: str = "show",
    ) -> Optional[str]:
        """
        Crée un nouveau libellé

        Args:
            name (str): Nom du libellé
            label_list_visibility (str): Visibilité dans la liste des libellés
            message_list_visibility (str): Visibilité dans la liste des messages

        Returns:
            str: ID du libellé créé ou None en cas d'erreur
        """
        try:
            label_object = {
                "name": name,
                "labelListVisibility": label_list_visibility,
                "messageListVisibility": message_list_visibility,
            }

            created_label = (
                self.service.users()
                .labels()
                .create(userId="me", body=label_object)
                .execute()
            )

            label_id = created_label["id"]
            logger.info(f"Libellé créé: {name} (ID: {label_id})")
            return label_id

        except HttpError as error:
            logger.error(f"Erreur lors de la création du libellé '{name}': {error}")
            return None

    def get_label_id(self, label_name: str) -> Optional[str]:
        """
        Récupère l'ID d'un libellé par son nom

        Args:
            label_name (str): Nom du libellé

        Returns:
            str: ID du libellé ou None si non trouvé
        """
        labels = self.get_labels()

        for label in labels:
            if label["name"] == label_name:
                return label["id"]

        logger.warning(f"Libellé '{label_name}' non trouvé")
        return None

    def list_emails(
        self, query: str = "", max_results: int = 10, include_spam_trash: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Liste les emails selon les critères

        Args:
            query (str): Requête de recherche Gmail
            max_results (int): Nombre maximum de résultats
            include_spam_trash (bool): Inclure spam et corbeille

        Returns:
            List[Dict]: Liste des emails avec leurs métadonnées
        """
        try:
            results = (
                self.service.users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    maxResults=max_results,
                    includeSpamTrash=include_spam_trash,
                )
                .execute()
            )

            messages = results.get("messages", [])
            emails = []

            for message in messages:
                email_data = self.get_email_details(message["id"])
                if email_data:
                    emails.append(email_data)

            logger.info(f"Récupération de {len(emails)} emails")
            return emails

        except HttpError as error:
            logger.error(f"Erreur lors de la récupération des emails: {error}")
            return []

    def get_email_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les détails d'un email spécifique

        Args:
            message_id (str): ID du message

        Returns:
            Dict: Détails de l'email ou None en cas d'erreur
        """
        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            headers = message["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "")
            date = next((h["value"] for h in headers if h["name"] == "Date"), "")

            # Extraction du contenu (texte et HTML)
            bodies = self._extract_email_bodies(message["payload"])

            email_data = {
                "id": message_id,
                "threadId": message.get("threadId", ""),
                "subject": subject,
                "sender": sender,
                "date": date,
                "body_text": bodies.get("text", ""),
                "body_html": bodies.get("html", ""),
                "body": bodies.get("text") or bodies.get("html") or "",
                "labels": message.get("labelIds", []),
                "snippet": message.get("snippet", ""),
                "internalDate": message.get("internalDate", ""),
                "is_read": "UNREAD" not in message.get("labelIds", []),
            }

            return email_data

        except HttpError as error:
            logger.error(
                f"Erreur lors de la récupération de l'email {message_id}: {error}"
            )
            return None

    def _extract_email_body(self, payload: Dict) -> str:
        """
        Extrait le contenu du corps de l'email

        Args:
            payload (Dict): Payload du message

        Returns:
            str: Contenu du corps de l'email (texte si possible, sinon HTML)
        """
        bodies = self._extract_email_bodies(payload)
        return bodies.get("text") or bodies.get("html") or ""

    def _extract_email_bodies(self, payload: Dict) -> Dict[str, str]:
        """
        Retourne les deux variantes du corps: texte et HTML.
        """
        text = ""
        html = ""

        def walk(part: Dict):
            nonlocal text, html
            mime = part.get("mimeType", "")
            body = part.get("body", {}) or {}
            data = body.get("data")
            filename = part.get("filename")
            if data and not filename:
                content = base64.urlsafe_b64decode(data).decode(
                    "utf-8", errors="replace"
                )
                if mime == "text/plain" and not text:
                    text = content
                elif mime == "text/html" and not html:
                    html = content
            for sub in part.get("parts", []) or []:
                walk(sub)

        walk(payload)
        return {"text": text, "html": html}

    def download_attachments_from_emails(
        self, emails: List[Dict[str, Any]], output_dir: str
    ) -> int:
        """
        Télécharge les pièces jointes des emails fournis et log un aperçu du contenu.

        Args:
            emails (List[Dict]): Liste d'emails (issus de get_email_details/list_emails)
            output_dir (str): Dossier cible de sauvegarde

        Returns:
            int: Nombre de pièces jointes sauvegardées
        """
        if not getattr(self, "service", None):
            logger.error(
                "Service Gmail non initialisé: impossible de télécharger les pièces jointes"
            )
            return 0

        service = self.service
        saved_count = 0
        for email in emails:
            try:
                message_id = email.get("id")
                if not message_id:
                    continue

                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=message_id, format="full")
                    .execute()
                )
                payload = msg.get("payload", {})
                parts = payload.get("parts", [])

                for part in parts or []:
                    filename = part.get("filename")
                    body = part.get("body", {})
                    attachment_id = body.get("attachmentId")
                    if filename and attachment_id:
                        attachment = (
                            service.users()
                            .messages()
                            .attachments()
                            .get(userId="me", messageId=message_id, id=attachment_id)
                            .execute()
                        )
                        data = attachment.get("data")
                        if not data:
                            continue
                        file_bytes = base64.urlsafe_b64decode(data)
                        os.makedirs(output_dir, exist_ok=True)
                        save_path = os.path.join(output_dir, filename)
                        with open(save_path, "wb") as f:
                            f.write(file_bytes)
                        saved_count += 1
            except Exception as e:
                logger.warning(
                    f"Erreur lors du traitement de l'email '{email.get('id')}': {e}"
                )
        return saved_count

    def mark_as_read(self, message_ids: List[str]) -> bool:
        """
        Marque des emails comme lus

        Args:
            message_ids (List[str]): Liste des IDs des messages

        Returns:
            bool: True si succès, False sinon
        """
        try:
            self.service.users().messages().modify(
                userId="me",
                id=",".join(message_ids),
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()

            logger.info(f"Marquage comme lu de {len(message_ids)} emails")
            return True

        except HttpError as error:
            logger.error(f"Erreur lors du marquage comme lu: {error}")
            return False

    def mark_as_unread(self, message_ids: List[str]) -> bool:
        """
        Marque des emails comme non lus

        Args:
            message_ids (List[str]): Liste des IDs des messages

        Returns:
            bool: True si succès, False sinon
        """
        try:
            self.service.users().messages().modify(
                userId="me", id=",".join(message_ids), body={"addLabelIds": ["UNREAD"]}
            ).execute()

            logger.info(f"Marquage comme non lu de {len(message_ids)} emails")
            return True

        except HttpError as error:
            logger.error(f"Erreur lors du marquage comme non lu: {error}")
            return False

    def add_labels(self, message_ids: List[str], label_names: List[str]) -> bool:
        """
        Ajoute des libellés à des emails

        Args:
            message_ids (List[str]): Liste des IDs des messages
            label_names (List[str]): Liste des noms des libellés

        Returns:
            bool: True si succès, False sinon
        """
        try:
            label_ids = []

            for label_name in label_names:
                label_id = self.get_label_id(label_name)
                if not label_id:
                    # Création du libellé s'il n'existe pas
                    label_id = self.create_label(label_name)
                    if not label_id:
                        logger.error(f"Impossible de créer le libellé '{label_name}'")
                        continue

                label_ids.append(label_id)

            if label_ids:
                self.service.users().messages().modify(
                    userId="me",
                    id=",".join(message_ids),
                    body={"addLabelIds": label_ids},
                ).execute()

                logger.info(
                    f"Ajout des libellés {label_names} à {len(message_ids)} emails"
                )
                return True

            return False

        except HttpError as error:
            logger.error(f"Erreur lors de l'ajout des libellés: {error}")
            return False

    def remove_labels(self, message_ids: List[str], label_names: List[str]) -> bool:
        """
        Retire des libellés d'emails

        Args:
            message_ids (List[str]): Liste des IDs des messages
            label_names (List[str]): Liste des noms des libellés

        Returns:
            bool: True si succès, False sinon
        """
        try:
            label_ids = []

            for label_name in label_names:
                label_id = self.get_label_id(label_name)
                if label_id:
                    label_ids.append(label_id)

            if label_ids:
                self.service.users().messages().modify(
                    userId="me",
                    id=",".join(message_ids),
                    body={"removeLabelIds": label_ids},
                ).execute()

                logger.info(
                    f"Retrait des libellés {label_names} de {len(message_ids)} emails"
                )
                return True

            return False

        except HttpError as error:
            logger.error(f"Erreur lors du retrait des libellés: {error}")
            return False

    def search_emails(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Recherche d'emails avec une requête Gmail

        Args:
            query (str): Requête de recherche (ex: "from:example@gmail.com", "subject:facture")
            max_results (int): Nombre maximum de résultats

        Returns:
            List[Dict]: Liste des emails correspondants
        """
        return self.list_emails(query=query, max_results=max_results)

    def get_unread_emails(self, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Récupère les emails non lus

        Args:
            max_results (int): Nombre maximum de résultats

        Returns:
            List[Dict]: Liste des emails non lus
        """
        return self.list_emails(query="is:unread", max_results=max_results)

    def get_emails_by_label(
        self, label_name: str, max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Récupère les emails d'un libellé spécifique

        Args:
            label_name (str): Nom du libellé
            max_results (int): Nombre maximum de résultats

        Returns:
            List[Dict]: Liste des emails du libellé
        """
        return self.list_emails(query=f"label:{label_name}", max_results=max_results)


def main():
    """
    Exemple d'utilisation de la librairie Gmail
    """
    try:
        # Initialisation du gestionnaire Gmail
        gmail = GmailManager()

        # Affichage des libellés disponibles
        print("=== Libellés disponibles ===")
        labels = gmail.get_labels()
        for label in labels[:10]:  # Affiche les 10 premiers
            print(f"- {label['name']} (ID: {label['id']})")

        # Récupération des emails non lus
        print("\n=== Emails non lus ===")
        unread_emails = gmail.get_unread_emails(max_results=5)
        for email in unread_emails:
            print(f"De: {email['sender']}")
            print(f"Objet: {email['subject']}")
            print(f"Date: {email['date']}")
            print(f"Lu: {not email['is_read']}")
            print("-" * 50)

        # Exemple de marquage comme lu
        if unread_emails:
            email_ids = [email["id"] for email in unread_emails[:2]]
            if gmail.mark_as_read(email_ids):
                print(f"✅ {len(email_ids)} emails marqués comme lus")

        # Exemple de création et attribution de libellé
        test_label = "Test_Auto"
        if gmail.create_label(test_label):
            if unread_emails:
                email_ids = [unread_emails[0]["id"]]
                if gmail.add_labels(email_ids, [test_label]):
                    print(f"✅ Libellé '{test_label}' ajouté à l'email")

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution: {e}")


if __name__ == "__main__":
    main()
