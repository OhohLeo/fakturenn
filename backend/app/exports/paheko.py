"""Paheko exporter implementation.

Provides connectivity to Paheko accounting software API.
Creates accounting transactions from Records.
"""

from typing import Any

import httpx

from app.core.vault import VaultError, get_vault
from app.exports.base import (
    AuthenticationError,
    BaseExporter,
    ConnectionError,
    DuplicateError,
    ExportError,
)


class PahekoExporter(BaseExporter):
    """Paheko API exporter for creating accounting transactions.

    Configuration (from Exporter.config):
        api_url: Paheko instance API URL (e.g., https://myasso.paheko.cloud/api/)
        api_user: API username for Basic Auth
        vault_api_key_path: Path to API key in Vault (auto-filled)
        default_year_id: Default accounting year ID (optional)
        verify_ssl: Verify SSL certificates (default: true)
        duplicate_check: Check for existing transactions (default: true)
        duplicate_field: Record field to use for duplicate detection (default: "invoice_id")

    Vault paths:
        exporters/paheko/{exporter_id} - Contains api_url, api_user, api_key

    Paheko API Reference:
        - POST /api/accounting/transaction - Create transaction
        - GET /api/accounting/years - List fiscal years
        - GET /api/accounting/years/{id}/journal - Get journal entries
    """

    def __init__(self, exporter_id: str, config: dict[str, Any]):
        super().__init__(exporter_id, config)
        self._client: httpx.AsyncClient | None = None
        self._api_url: str = ""
        self._years_cache: list[dict[str, Any]] = []

    async def connect(self) -> None:
        """Connect to Paheko API using credentials from Vault."""
        try:
            vault = get_vault()

            # Load credentials from Vault
            creds = vault.get_paheko_credentials(self.exporter_id)
            if not creds:
                raise AuthenticationError(
                    "No Paheko credentials found in Vault",
                    {"exporter_id": self.exporter_id},
                )

            self._api_url = creds.get("api_url") or self.config.get("api_url", "")
            if not self._api_url:
                raise ConnectionError("No api_url configured")

            # Ensure URL ends with /
            if not self._api_url.endswith("/"):
                self._api_url += "/"

            api_user = creds.get("api_user") or self.config.get("api_user", "")
            api_key = creds.get("api_key", "")

            # Create HTTP client with Basic Auth
            auth = (api_user, api_key) if api_user else None
            verify_ssl = self.config.get("verify_ssl", True)

            self._client = httpx.AsyncClient(
                base_url=self._api_url,
                auth=auth,
                verify=verify_ssl,
                timeout=30.0,
            )

            # Test connection by fetching years
            await self._fetch_years()
            self._connected = True

        except VaultError as e:
            raise AuthenticationError(
                f"Failed to load credentials from Vault: {e}",
                {"exporter_id": self.exporter_id},
            ) from e
        except httpx.HTTPError as e:
            raise ConnectionError(
                f"Failed to connect to Paheko API: {e}",
                {"exporter_id": self.exporter_id, "api_url": self._api_url},
            ) from e

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
        self._client = None
        self._connected = False
        self._years_cache = []

    async def _fetch_years(self) -> list[dict[str, Any]]:
        """Fetch accounting years from Paheko."""
        if self._years_cache:
            return self._years_cache

        if not self._client:
            raise ConnectionError("Not connected to Paheko API")

        try:
            response = await self._client.get("accounting/years")
            response.raise_for_status()
            self._years_cache = response.json()
            return self._years_cache
        except httpx.HTTPError as e:
            raise ExportError(f"Failed to fetch years: {e}") from e

    async def get_accounting_years(self) -> list[dict[str, Any]]:
        """Get list of accounting years.

        Returns:
            List of year dicts with id, label, start_date, end_date
        """
        return await self._fetch_years()

    async def create_entry(self, data: dict[str, Any]) -> str:
        """Create an accounting transaction in Paheko.

        Args:
            data: Transaction data with keys:
                - id_year: Accounting year ID
                - label: Transaction label
                - date: Transaction date (YYYY-MM-DD)
                - type: Transaction type (EXPENSE, REVENUE, TRANSFER, ADVANCED)
                - amount: Transaction amount (decimal)
                - debit: Debit account code
                - credit: Credit account code
                - reference: Optional reference (for duplicate detection)

        Returns:
            ID of created transaction

        Raises:
            ExportError: If creation fails
            DuplicateError: If transaction already exists
        """
        if not self._client:
            raise ConnectionError("Not connected to Paheko API")

        # Check for duplicates if enabled
        if self.config.get("duplicate_check", True):
            reference = data.get("reference", "")
            if reference and await self.check_duplicate(reference):
                raise DuplicateError(
                    f"Transaction with reference '{reference}' already exists",
                    {"reference": reference},
                )

        try:
            # Prepare transaction payload
            payload = {
                "id_year": data["id_year"],
                "label": data["label"],
                "date": data["date"],
                "type": data.get("type", "EXPENSE"),
            }

            # Add lines for simple transaction
            if "amount" in data:
                payload["lines"] = [
                    {
                        "account": data["debit"],
                        "debit": data["amount"],
                        "credit": 0,
                    },
                    {
                        "account": data["credit"],
                        "debit": 0,
                        "credit": data["amount"],
                    },
                ]

            # Add reference if provided
            if data.get("reference"):
                payload["reference"] = data["reference"]

            response = await self._client.post(
                "accounting/transaction",
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            return str(result.get("id", ""))

        except httpx.HTTPStatusError as e:
            raise ExportError(
                f"Failed to create transaction: {e.response.text}",
                {"status_code": e.response.status_code},
            ) from e
        except httpx.HTTPError as e:
            raise ExportError(f"HTTP error creating transaction: {e}") from e

    async def check_duplicate(self, identifier: str) -> bool:
        """Check if a transaction with given reference exists.

        Args:
            identifier: Reference to check (usually invoice_id)

        Returns:
            True if transaction exists, False otherwise
        """
        if not self._client:
            raise ConnectionError("Not connected to Paheko API")

        try:
            # Search in all years
            years = await self.get_accounting_years()
            for year in years:
                year_id = year.get("id")
                if not year_id:
                    continue

                # Get journal for this year
                response = await self._client.get(
                    f"accounting/years/{year_id}/journal"
                )
                response.raise_for_status()

                journal = response.json()
                for entry in journal:
                    if entry.get("reference") == identifier:
                        return True

            return False

        except httpx.HTTPError:
            # If we can't check, assume no duplicate
            return False

    async def match_fiscal_year(self, transaction_date: str) -> int | None:
        """Find the fiscal year that contains the given date.

        Args:
            transaction_date: Date in YYYY-MM-DD format

        Returns:
            Year ID if found, None otherwise
        """
        from datetime import datetime

        date_obj = datetime.strptime(transaction_date, "%Y-%m-%d").date()
        years = await self.get_accounting_years()

        for year in years:
            start_date = datetime.strptime(year["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(year["end_date"], "%Y-%m-%d").date()

            if start_date <= date_obj <= end_date:
                return year["id"]

        return None
