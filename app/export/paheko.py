import requests
from typing import Dict, List, Optional, Union
from datetime import datetime


class PahekoClient:
    """
    Client pour l'API Paheko permettant de gérer les transactions comptables.

    Documentation: https://paheko.cloud/api#authentification
    """

    def __init__(self, base_url: str, username: str, password: str):
        """
        Initialise le client Paheko.

        Args:
            base_url: URL de base de l'association (ex: https://monasso.paheko.cloud)
            username: Nom d'utilisateur pour l'API
            password: Mot de passe pour l'API
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = (username, password)

    def _get_api_url(self, endpoint: str) -> str:
        """Construit l'URL complète pour un endpoint de l'API."""
        return f"{self.base_url}/api/{endpoint}"

    def create_transaction(
        self,
        id_year: int,
        label: str,
        date: Union[str, datetime],
        transaction_type: str,
        amount: Optional[float] = None,
        credit: Optional[str] = None,
        debit: Optional[str] = None,
        lines: Optional[List[Dict]] = None,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
        id_project: Optional[int] = None,
        payment_reference: Optional[str] = None,
        linked_users: Optional[List[int]] = None,
        linked_transactions: Optional[List[int]] = None,
        linked_subscriptions: Optional[List[int]] = None,
    ) -> Dict:
        """
        Crée une nouvelle transaction comptable.

        Args:
            id_year: ID de l'exercice comptable
            label: Libellé de l'écriture
            date: Date de l'écriture (format YYYY-MM-DD ou objet datetime)
            transaction_type: Type d'écriture ('EXPENSE', 'REVENUE', 'TRANSFER', 'DEBT', 'CREDIT', 'ADVANCED')
            amount: Montant de l'écriture (pour les écritures simplifiées)
            credit: Numéro du compte porté au crédit (pour les écritures simplifiées)
            debit: Numéro du compte porté au débit (pour les écritures simplifiées)
            lines: Lignes d'écriture pour les écritures multi-lignes (type ADVANCED)
            reference: Numéro de pièce comptable
            notes: Remarques (texte multi-ligne)
            id_project: ID unique du projet à affecter
            payment_reference: Référence de paiement (pour les écritures simplifiées)
            linked_users: Liste des IDs des membres à lier à l'écriture
            linked_transactions: Liste des IDs des écritures à lier
            linked_subscriptions: Liste des IDs des inscriptions à lier

        Returns:
            Dict contenant les détails de la transaction créée

        Raises:
            requests.RequestException: En cas d'erreur HTTP
            ValueError: En cas de paramètres invalides
        """
        # Validation des paramètres
        if transaction_type not in [
            "EXPENSE",
            "REVENUE",
            "TRANSFER",
            "DEBT",
            "CREDIT",
            "ADVANCED",
        ]:
            raise ValueError(f"Type de transaction invalide: {transaction_type}")

        # Formatage de la date
        if isinstance(date, datetime):
            date_str = date.strftime("%Y-%m-%d")
        else:
            date_str = date

        # Préparation des données
        data = {
            "id_year": id_year,
            "label": label,
            "date": date_str,
            "type": transaction_type,
        }

        # Ajout des champs optionnels
        if reference:
            data["reference"] = reference
        if notes:
            data["notes"] = notes
        if id_project:
            data["id_project"] = id_project
        if linked_users:
            data["linked_users"] = linked_users
        if linked_transactions:
            data["linked_transactions"] = linked_transactions
        if linked_subscriptions:
            data["linked_subscriptions"] = linked_subscriptions

        # Gestion des écritures simplifiées vs multi-lignes
        if transaction_type == "ADVANCED":
            if not lines:
                raise ValueError(
                    "Les lignes d'écriture sont requises pour les écritures de type ADVANCED"
                )
            data["lines"] = lines
        else:
            # Écriture simplifiée
            if amount is None:
                raise ValueError("Le montant est requis pour les écritures simplifiées")
            data["amount"] = amount

            if credit:
                data["credit"] = credit
            if debit:
                data["debit"] = debit
            if payment_reference:
                data["payment_reference"] = payment_reference

        # Envoi de la requête
        url = self._get_api_url("accounting/transaction")
        response = self.session.post(url, json=data)

        if response.status_code in (200, 201):
            resp = response.json()
            return {"id": resp.get("id"), "lines": resp.get("lines", []), "raw": resp}
        else:
            error_msg = (
                f"Erreur lors de la création de la transaction: {response.status_code}"
            )
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg += f" - {error_data['error']}"
            except Exception:
                error_msg += f" - {response.text}"
            raise requests.RequestException(error_msg)

    def create_simple_expense(
        self,
        id_year: int,
        label: str,
        date: Union[str, datetime],
        amount: float,
        debit_account: str,
        credit_account: str,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
        payment_reference: Optional[str] = None,
    ) -> Dict:
        """
        Crée une dépense simplifiée (2 lignes).

        Args:
            id_year: ID de l'exercice comptable
            label: Libellé de l'écriture
            date: Date de l'écriture
            amount: Montant de la dépense
            debit_account: Compte de débit (ex: "601" pour achats)
            credit_account: Compte de crédit (ex: "512A" pour banque)
            reference: Numéro de pièce comptable
            notes: Remarques
            payment_reference: Référence de paiement

        Returns:
            Dict contenant les détails de la transaction créée
        """
        return self.create_transaction(
            id_year=id_year,
            label=label,
            date=date,
            transaction_type="EXPENSE",
            amount=amount,
            debit=debit_account,
            credit=credit_account,
            reference=reference,
            notes=notes,
            payment_reference=payment_reference,
        )

    def create_simple_revenue(
        self,
        id_year: int,
        label: str,
        date: Union[str, datetime],
        amount: float,
        debit_account: str,
        credit_account: str,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
        payment_reference: Optional[str] = None,
    ) -> Dict:
        """
        Crée une recette simplifiée (2 lignes).

        Args:
            id_year: ID de l'exercice comptable
            label: Libellé de l'écriture
            date: Date de l'écriture
            amount: Montant de la recette
            debit_account: Compte de débit (ex: "512A" pour banque)
            credit_account: Compte de crédit (ex: "706" pour prestations de services)
            reference: Numéro de pièce comptable
            notes: Remarques
            payment_reference: Référence de paiement

        Returns:
            Dict contenant les détails de la transaction créée
        """
        return self.create_transaction(
            id_year=id_year,
            label=label,
            date=date,
            transaction_type="REVENUE",
            amount=amount,
            debit=debit_account,
            credit=credit_account,
            reference=reference,
            notes=notes,
            payment_reference=payment_reference,
        )

    def create_transfer(
        self,
        id_year: int,
        label: str,
        date: Union[str, datetime],
        amount: float,
        debit_account: str,
        credit_account: str,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict:
        """
        Crée un virement entre comptes.

        Args:
            id_year: ID de l'exercice comptable
            label: Libellé de l'écriture
            date: Date de l'écriture
            amount: Montant du virement
            debit_account: Compte de débit
            credit_account: Compte de crédit
            reference: Numéro de pièce comptable
            notes: Remarques

        Returns:
            Dict contenant les détails de la transaction créée
        """
        return self.create_transaction(
            id_year=id_year,
            label=label,
            date=date,
            transaction_type="TRANSFER",
            amount=amount,
            debit=debit_account,
            credit=credit_account,
            reference=reference,
            notes=notes,
        )

    def create_advanced_transaction(
        self,
        id_year: int,
        label: str,
        date: Union[str, datetime],
        lines: List[Dict],
        reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict:
        """
        Crée une écriture multi-lignes (avancée).

        Args:
            id_year: ID de l'exercice comptable
            label: Libellé de l'écriture
            date: Date de l'écriture
            lines: Liste des lignes d'écriture, chaque ligne doit contenir:
                   - account (numéro du compte) ou id_account (ID unique du compte)
                   - credit: montant au crédit (0 si debit renseigné)
                   - debit: montant au débit
                   - label (optionnel): libellé de la ligne
                   - reference (optionnel): référence de la ligne
                   - id_project (optionnel): ID du projet
            reference: Numéro de pièce comptable
            notes: Remarques

        Returns:
            Dict contenant les détails de la transaction créée
        """
        return self.create_transaction(
            id_year=id_year,
            label=label,
            date=date,
            transaction_type="ADVANCED",
            lines=lines,
            reference=reference,
            notes=notes,
        )

    def get_transaction(self, transaction_id: int) -> Dict:
        """
        Récupère les détails d'une transaction.

        Args:
            transaction_id: ID de la transaction

        Returns:
            Dict contenant les détails de la transaction
        """
        url = self._get_api_url(f"accounting/transaction/{transaction_id}")
        response = self.session.get(url)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f"Erreur lors de la récupération de la transaction: {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg += f" - {error_data['error']}"
            except Exception:
                error_msg += f" - {response.text}"
            raise requests.RequestException(error_msg)

    def get_accounting_years(self) -> List[Dict]:
        """
        Récupère la liste des exercices comptables.

        Returns:
            Liste des exercices comptables
        """
        url = self._get_api_url("accounting/years")
        response = self.session.get(url)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = (
                f"Erreur lors de la récupération des exercices: {response.status_code}"
            )
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg += f" - {error_data['error']}"
            except Exception:
                error_msg += f" - {response.text}"
            raise requests.RequestException(error_msg)

    def get_account_journal(
        self,
        id_year: Union[int, str],
        code: Optional[str] = None,
        id_account: Optional[int] = None,
    ) -> List[Dict]:
        """
        Renvoie le journal des écritures d'un compte pour l'exercice indiqué.

        Args:
            id_year: ID de l'exercice comptable, ou 'current' pour l'exercice ouvert en cours
            code: Code du compte (ex: '512A', '626')
            id_account: ID interne du compte

        Returns:
            Liste des écritures du journal pour le compte

        Raises:
            ValueError: si ni 'code' ni 'id_account' n'est fourni
            requests.RequestException: en cas d'erreur HTTP
        """
        if code is None and id_account is None:
            raise ValueError("Paramètre requis: 'code' ou 'id_account'")

        params: Dict[str, Union[str, int]] = {}
        if code is not None:
            params["code"] = code
        if id_account is not None:
            params["id"] = id_account

        url = self._get_api_url(f"accounting/years/{id_year}/account/journal")
        response = self.session.get(url, params=params)

        if response.status_code == 200:
            try:
                return response.json()
            except Exception as e:
                raise requests.RequestException(f"Réponse JSON invalide: {e}")
        else:
            error_msg = (
                f"Erreur lors de la récupération du journal: {response.status_code}"
            )
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg += f" - {error_data['error']}"
            except Exception:
                error_msg += f" - {response.text}"
            raise requests.RequestException(error_msg)


# Exemple d'utilisation
if __name__ == "__main__":
    # Configuration du client
    client = PahekoClient(
        base_url="https://monasso.paheko.cloud",
        username="api_user",
        password="api_password",
    )

    # Exemple: Créer une dépense
    try:
        transaction = client.create_simple_expense(
            id_year=1,
            label="Achat fournitures de bureau",
            date="2024-01-15",
            amount=150.00,
            debit_account="601",  # Achats
            credit_account="512A",  # Banque
            reference="FAC-2024-001",
            notes="Fournitures pour le bureau",
        )
        print(f"Transaction créée: {transaction}")

    except Exception as e:
        print(f"Erreur: {e}")
