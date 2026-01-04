"""Record2Paheko mapper implementation.

Transforms Records into Paheko accounting transactions.
"""

import calendar
from typing import Any

from app.exports.base import DuplicateError
from app.exports.paheko import PahekoExporter
from app.mappers.base import BaseMapper, TransformationError
from app.models import Record


# French month names for label templates
FRENCH_MONTHS = [
    "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
]


class Record2PahekoMapper(BaseMapper):
    """Mapper that transforms Records into Paheko transactions.

    Rules schema (from Mapper.transformation_logic JSONB):
        transaction_type: Paheko transaction type
            EXPENSE, REVENUE, TRANSFER, ADVANCED

        label_template: Template for transaction label
            e.g., "{invoice_id} - {month} {year}"

        debit_account: Paheko account code for debit
            e.g., "601"

        credit_account: Paheko account code for credit
            e.g., "512A"

        reference_field: Record field to use as transaction reference
            e.g., "invoice_id" (for duplicate detection)

        amount_field: Record field containing the amount
            e.g., "amount_text"

        year_matching: How to match fiscal year
            "auto" - Match by record.date
            "fixed" - Use fixed_year_id

        fixed_year_id: Paheko year ID (only if year_matching is "fixed")

        amount_parsing: Amount string parsing configuration
            decimal_separator: "," or "."
            thousands_separator: " ", ".", "," or ""
            currency_symbol: "€" or other symbol to strip

    Example rules:
        {
            "transaction_type": "EXPENSE",
            "label_template": "{invoice_id} - {month} {year}",
            "debit_account": "601",
            "credit_account": "512A",
            "reference_field": "invoice_id",
            "amount_field": "amount_text",
            "year_matching": "auto",
            "amount_parsing": {
                "decimal_separator": ",",
                "thousands_separator": " ",
                "currency_symbol": "€"
            }
        }
    """

    exporter: PahekoExporter

    async def transform_and_export(self, record: Record) -> bool:
        """Transform Record and export to Paheko.

        Args:
            record: Record to transform and export

        Returns:
            True if export succeeded, False if skipped (duplicate)

        Raises:
            TransformationError: If transformation fails
        """
        # Build context for template rendering
        context = self._build_context(record)

        # Check for duplicates
        reference_field = self.rules.get("reference_field", "invoice_id")
        reference = (record.data or {}).get(reference_field, "")
        if reference:
            try:
                if await self.exporter.check_duplicate(str(reference)):
                    return False  # Skip duplicate
            except Exception:
                pass  # Continue if check fails

        # Get fiscal year
        year_id = await self._get_fiscal_year(record)
        if not year_id:
            raise TransformationError(
                f"No matching fiscal year for date {record.date}",
                {"record_id": str(record.id), "date": str(record.date)},
            )

        # Build label from template
        label_template = self.rules.get("label_template", "{invoice_id}")
        label = self._render_template(label_template, context)

        # Parse amount
        amount_field = self.rules.get("amount_field", "amount_text")
        amount_str = (record.data or {}).get(amount_field, "0")
        amount = self._parse_amount(str(amount_str))

        if amount <= 0:
            raise TransformationError(
                f"Invalid amount: {amount_str}",
                {"record_id": str(record.id), "amount_str": amount_str},
            )

        # Build transaction data
        transaction_data = {
            "id_year": year_id,
            "label": label,
            "date": record.date.isoformat(),
            "type": self.rules.get("transaction_type", "EXPENSE"),
            "amount": amount,
            "debit": self.rules.get("debit_account", ""),
            "credit": self.rules.get("credit_account", ""),
            "reference": str(reference) if reference else "",
        }

        # Validate required fields
        if not transaction_data["debit"] or not transaction_data["credit"]:
            raise TransformationError(
                "Missing debit or credit account in rules",
                {"record_id": str(record.id)},
            )

        # Export transaction
        try:
            await self.exporter.create_entry(transaction_data)
            return True
        except DuplicateError:
            return False

    def _build_context(self, record: Record) -> dict[str, Any]:
        """Build template context from record."""
        context: dict[str, Any] = {}

        # Add record data fields
        if record.data:
            context.update(record.data)

        # Add date-based fields
        if record.date:
            context["date"] = record.date.isoformat()
            context["year"] = record.date.year
            context["month"] = FRENCH_MONTHS[record.date.month]
            context["month_num"] = f"{record.date.month:02d}"
            context["day"] = f"{record.date.day:02d}"

        return context

    async def _get_fiscal_year(self, record: Record) -> int | None:
        """Get fiscal year ID for record date."""
        year_matching = self.rules.get("year_matching", "auto")

        if year_matching == "fixed":
            return self.rules.get("fixed_year_id")

        # Auto match by date
        return await self.exporter.match_fiscal_year(record.date.isoformat())
