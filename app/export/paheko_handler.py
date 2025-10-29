"""Paheko export handler for accounting integration."""

import logging
from typing import Any, Dict, Optional
from datetime import datetime

from app.export.base import ExportHandler, ExportResult
from app.export.paheko import PahekoClient
from app.core.vault_client import VaultClient

logger = logging.getLogger(__name__)


class PahekoExportHandler(ExportHandler):
    """Handler for exporting invoices to Paheko accounting software."""

    def __init__(
        self,
        config: Dict[str, Any],
        vault_client: Optional[VaultClient] = None,
    ):
        """Initialize Paheko export handler.

        Args:
            config: Export configuration with:
                - paheko_type: EXPENSE, REVENUE, TRANSFER, ADVANCED
                - label_template: Template with placeholders
                - debit: Debit account code(s)
                - credit: Credit account code(s)
            vault_client: Vault client for Paheko credentials
        """
        super().__init__(config)
        self.vault_client = vault_client
        self.paheko_client: Optional[PahekoClient] = None

    async def export(
        self,
        invoice_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> ExportResult:
        """Export invoice to Paheko.

        Args:
            invoice_data: Invoice data with file_path, amount_eur, etc.
            context: Context with {invoice_id, date, amount_eur, month, year, quarter}

        Returns:
            ExportResult with Paheko transaction ID
        """
        try:
            if not self._validate_invoice_data(invoice_data):
                return ExportResult(
                    status="failed",
                    error_message="Missing required invoice data fields",
                )

            if not self._validate_context(context):
                return ExportResult(
                    status="failed",
                    error_message="Missing required context fields",
                )

            # Initialize Paheko client if not already done
            if not self.paheko_client:
                self.paheko_client = await self._init_paheko_client()
                if not self.paheko_client:
                    return ExportResult(
                        status="failed",
                        error_message="Failed to initialize Paheko client",
                    )

            # Build transaction label from template
            label = self.config.get("label_template", "Facture {invoice_id}").format(
                **context
            )

            # Get accounting year (TODO: make this configurable or discover from date)
            id_year = await self._get_accounting_year(context.get("date"))
            if not id_year:
                return ExportResult(
                    status="failed",
                    error_message="No matching accounting year found",
                )

            # Check for duplicates
            duplicate_check = await self._check_duplicate(
                id_year, label, context.get("date")
            )
            if duplicate_check:
                logger.info(f"Duplicate entry detected: {label}")
                return ExportResult(
                    status="duplicate_skipped",
                    external_reference=None,
                    error_message="Duplicate entry already exists",
                )

            # Create transaction
            transaction = await self._create_transaction(
                id_year=id_year,
                label=label,
                date=context.get("date"),
                amount=invoice_data.get("amount_eur"),
            )

            if transaction and isinstance(transaction, dict) and "id" in transaction:
                logger.info(f"Created Paheko transaction: {transaction['id']}")
                return ExportResult(
                    status="success",
                    external_reference=str(transaction["id"]),
                )
            else:
                return ExportResult(
                    status="failed",
                    error_message="Failed to create transaction in Paheko",
                )

        except Exception as e:
            logger.error(f"Paheko export failed: {e}")
            return ExportResult(
                status="failed",
                error_message=str(e),
            )

    async def _init_paheko_client(self) -> Optional[PahekoClient]:
        """Initialize Paheko client with credentials.

        Returns:
            PahekoClient instance or None if initialization fails
        """
        try:
            if not self.vault_client:
                logger.error("Vault client required for Paheko credentials")
                return None

            # Retrieve Paheko credentials from Vault
            paheko_secret = self.vault_client.get_secret("secret/data/fakturenn/paheko/credentials")
            if not paheko_secret:
                logger.error("Paheko credentials not found in Vault")
                return None

            base_url = paheko_secret.get("base_url") or self.config.get("base_url")
            username = paheko_secret.get("username")
            password = paheko_secret.get("password")

            if not all([base_url, username, password]):
                logger.error("Missing Paheko credentials")
                return None

            client = PahekoClient(base_url, username, password)
            logger.info("Paheko client initialized")
            return client

        except Exception as e:
            logger.error(f"Failed to initialize Paheko client: {e}")
            return None

    async def _get_accounting_year(self, date_str: str) -> Optional[int]:
        """Get Paheko accounting year ID for a date.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            Year ID or None if not found
        """
        try:
            years = self.paheko_client.get_accounting_years()
            if not years:
                logger.warning("No accounting years found in Paheko")
                return None

            # Parse date
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Find matching year
            for year in years:
                try:
                    start = datetime.strptime(year.get("start_date", ""), "%Y-%m-%d").date()
                    end = datetime.strptime(year.get("end_date", ""), "%Y-%m-%d").date()
                    if start <= date_obj <= end:
                        return year.get("id")
                except Exception:
                    continue

            logger.warning(f"No matching accounting year for date: {date_str}")
            return None

        except Exception as e:
            logger.error(f"Failed to get accounting year: {e}")
            return None

    async def _check_duplicate(
        self, id_year: int, label: str, date_str: str
    ) -> bool:
        """Check for duplicate transactions.

        Args:
            id_year: Accounting year ID
            label: Transaction label
            date_str: Transaction date

        Returns:
            True if duplicate found
        """
        try:
            # Get debit account code
            debit_codes = self.config.get("debit", "").split(",")
            if not debit_codes or not debit_codes[0].strip():
                return False

            account_code = debit_codes[0].strip()

            # Query account journal
            journal = self.paheko_client.get_account_journal(id_year, account_code)
            if not journal:
                return False

            # Look for matching entry
            for entry in journal:
                entry_date = entry.get("date", "")
                if isinstance(entry_date, dict):
                    entry_date = entry_date.get("date", "")
                entry_date = str(entry_date)[:10]  # Extract YYYY-MM-DD

                entry_label = entry.get("label", "")

                if entry_date == date_str and entry_label == label:
                    logger.info(f"Duplicate found: {label} on {date_str}")
                    return True

            return False

        except Exception as e:
            logger.warning(f"Failed to check duplicates: {e}")
            return False

    async def _create_transaction(
        self,
        id_year: int,
        label: str,
        date: str,
        amount: float,
    ) -> Optional[Dict]:
        """Create transaction in Paheko.

        Args:
            id_year: Accounting year ID
            label: Transaction label
            date: Transaction date
            amount: Transaction amount

        Returns:
            Transaction data or None if failed
        """
        try:
            debit_codes = [c.strip() for c in self.config.get("debit", "").split(",")]
            credit_codes = [c.strip() for c in self.config.get("credit", "").split(",")]

            debit = debit_codes[0] if debit_codes else None
            credit = credit_codes[0] if credit_codes else None

            if not debit or not credit:
                logger.error("Missing debit or credit account configuration")
                return None

            transaction = self.paheko_client.create_transaction(
                id_year=id_year,
                label=label,
                date=date,
                transaction_type=self.config.get("paheko_type", "EXPENSE"),
                amount=amount,
                debit=debit,
                credit=credit,
            )

            return transaction

        except Exception as e:
            logger.error(f"Failed to create Paheko transaction: {e}")
            return None
