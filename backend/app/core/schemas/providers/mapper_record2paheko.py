"""JSON Schema for Record2Paheko mapper configuration."""

SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Record2Paheko Mapper Configuration",
    "description": "Configuration for transforming records into Paheko transactions",
    "type": "object",
    "properties": {
        "transaction_type": {
            "type": "string",
            "title": "Transaction Type",
            "description": "Paheko transaction type",
            "enum": ["EXPENSE", "REVENUE", "TRANSFER", "ADVANCED"],
            "default": "EXPENSE",
        },
        "label_template": {
            "type": "string",
            "title": "Label Template",
            "description": "Template for transaction label (e.g., '{invoice_id} - {month} {year}')",
            "default": "{invoice_id} - {description}",
        },
        "debit_account": {
            "type": "string",
            "title": "Debit Account",
            "description": "Paheko account code for debit (e.g., '601')",
        },
        "credit_account": {
            "type": "string",
            "title": "Credit Account",
            "description": "Paheko account code for credit (e.g., '512A')",
        },
        "reference_field": {
            "type": "string",
            "title": "Reference Field",
            "description": "Record field to use as transaction reference (for duplicate detection)",
            "default": "invoice_id",
        },
        "amount_field": {
            "type": "string",
            "title": "Amount Field",
            "description": "Record field containing the amount",
            "default": "amount_text",
        },
        "year_matching": {
            "type": "string",
            "title": "Year Matching",
            "description": "How to match fiscal year",
            "enum": ["auto", "fixed"],
            "default": "auto",
        },
        "fixed_year_id": {
            "type": "integer",
            "title": "Fixed Year ID",
            "description": "Paheko year ID (only if year_matching is 'fixed')",
        },
        "amount_parsing": {
            "type": "object",
            "title": "Amount Parsing",
            "description": "How to parse amount values",
            "properties": {
                "decimal_separator": {
                    "type": "string",
                    "title": "Decimal Separator",
                    "description": "Decimal separator in amount strings",
                    "enum": [".", ","],
                    "default": ",",
                },
                "thousands_separator": {
                    "type": "string",
                    "title": "Thousands Separator",
                    "description": "Thousands separator in amount strings",
                    "enum": ["", " ", ".", ","],
                    "default": " ",
                },
                "currency_symbol": {
                    "type": "string",
                    "title": "Currency Symbol",
                    "description": "Currency symbol to strip (e.g., '€')",
                    "default": "€",
                },
            },
        },
    },
    "required": ["debit_account", "credit_account"],
}
