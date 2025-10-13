# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Fakturenn** is a Python-based automation suite for managing invoicing for a micro-crèche (Youn Ha Solena). It retrieves invoices from various sources (Free, Free Mobile, Gmail), extracts relevant data, and exports accounting entries to Paheko (accounting software).

**Technology Stack**: Python 3.12+, Poetry, Selenium (for web scraping), Google APIs (Sheets & Gmail), requests

## Development Commands

### Environment Setup
```bash
# Install dependencies
poetry install

# Load environment variables from .env file
# The project looks for .env in the project root with credentials like:
# FREE_LOGIN, FREE_PASSWORD, FREE_MOBILE_LOGIN, FREE_MOBILE_PASSWORD
# GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
# SHEETS_SPREADSHEET_ID, SHEETS_RANGE, SHEETS_CREDENTIALS, SHEETS_TOKEN
# PAHEKO_BASE_URL, PAHEKO_USER, PAHEKO_PASS
# FROM_DATE, OUTPUT_DIR, HEADLESS_MODE
```

### Running Scripts

```bash
# Main runner - processes invoices based on Google Sheets configuration
poetry run python scripts/run_fakturenn.py --help
poetry run fakturenn --help  # Alternative using project.scripts entry point

# Download Free (ISP) invoices
poetry run python scripts/download_free_invoices.py --help
poetry run python scripts/download_free_invoices.py

# Setup Free Mobile authentication
poetry run python scripts/setup_free_mobile_auth.py --help
poetry run python scripts/setup_free_mobile_auth.py

# List/process unread Gmail messages
poetry run python scripts/gmail_unread.py --help
poetry run python scripts/gmail_unread.py
```

### Code Quality
```bash
# Lint and format with ruff
poetry run ruff check .
poetry run ruff format .
```

## Architecture

### Core Flow (FakturennRunner)

The main entry point `scripts/run_fakturenn.py` orchestrates the complete workflow:

1. **Load Configuration** from Google Sheets (`app/core/google_sheets.py`)
   - Reads structured config with columns: `origin`, `from`, `subject`, `fakturenn_extraction`, `fakturenn_extraction_params`, `paheko_type`, `paheko_label`, `paheko_debit`, `paheko_credit`
   - Each row defines a source to monitor and how to export to Paheko

2. **Execute Sources** via `SourceRunner` (`app/sources/runner.py`)
   - Supports multiple source types: `FreeInvoice`, `FreeMobileInvoice`, `Gmail`
   - Downloads invoices and extracts metadata (date, amount, invoice ID)

3. **Export to Paheko** (`app/export/paheko.py`)
   - Creates accounting transactions via Paheko API
   - Supports transaction types: EXPENSE, REVENUE, TRANSFER, ADVANCED
   - Includes duplicate detection by checking account journal

### Key Components

#### Sources (`app/sources/`)
- **`invoice.py`**: `Invoice` dataclass - universal representation of an invoice
- **`free.py`**: `FreeInvoiceDownloader` - scrapes Free ISP invoices using Selenium
- **`free_mobile.py`**: `FreeMobileInvoiceDownloader` - retrieves Free Mobile invoices via Gmail
- **`gmail_manager.py`**: `GmailManager` - Gmail API wrapper for searching emails, downloading attachments
- **`runner.py`**: `SourceRunner` - executes source-specific logic, filters by date, extracts data using regex patterns

#### Core (`app/core/`)
- **`runner.py`**: `FakturennRunner` - main orchestrator connecting Google Sheets config, sources, and Paheko export
- **`google_sheets.py`**: `GoogleSheetsConfigLoader` - reads configuration from Google Sheets
- **`paheko_helpers.py`**: Helper functions for parsing debit/credit accounts and building transaction payloads
- **`date_utils.py`**: Date parsing utilities supporting multiple formats (ISO, French dates, month names)

#### Export (`app/export/`)
- **`paheko.py`**: `PahekoClient` - REST API client for Paheko accounting software
  - Methods: `create_transaction()`, `create_simple_expense()`, `create_simple_revenue()`, `create_transfer()`, `create_advanced_transaction()`
  - Includes `get_accounting_years()` and `get_account_journal()` for duplicate detection

### Data Flow Example

1. User runs: `poetry run fakturenn --from 2025-01-01 --sheets-id ABC123`
2. `FakturennRunner` loads config rows from Google Sheets
3. For each config row:
   - `SourceRunner.run()` downloads invoices from the specified source
   - Filters invoices by `from_date`
   - Extracts structured data (date, amount, ID) using regex patterns from `fakturenn_extraction_params`
4. For each downloaded invoice:
   - Matches invoice date to a Paheko accounting year
   - Builds transaction payload using `PahekoMapping` (label template, debit/credit accounts)
   - Checks for duplicates in account journal
   - Creates transaction via `PahekoClient.create_transaction()`

### Gmail Source Extraction

The Gmail source uses regex patterns defined in `fakturenn_extraction_params` (from Google Sheets) to extract invoice data from email bodies. Patterns can target:
- `email_html`: Match against HTML body (`body_html`)
- `email_text`: Match against plain text body (`body_text`)

Named capture groups in regex:
- `(?P<invoice_id>...)`: Extracts invoice identifier
- `(?P<date>...)`: Extracts invoice date (falls back to email date)
- `(?P<amount_text>...)`: Extracts amount text (parsed to float)

Note: The code converts JavaScript-style `(?<name>...)` to Python `(?P<name>...)`.

## Configuration

### Google Sheets Format

Expected columns in the config sheet:
- `origin`: Logical source name (used for filtering with `--origin`)
- `from`: Email sender (for Gmail source)
- `subject`: Email subject filter (for Gmail source)
- `fakturenn_extraction`: Source type (`FreeInvoice`, `FreeMobileInvoice`, `Gmail`)
- `fakturenn_extraction_params`: JSON with extraction config (e.g., regex patterns for Gmail)
- `paheko_type`: Transaction type (`EXPENSE`, `REVENUE`, `TRANSFER`, `ADVANCED`)
- `paheko_label`: Label template with placeholders: `{invoice_id}`, `{month}`, `{date}`, `{year}`
- `paheko_debit`: Debit account(s), comma/newline separated
- `paheko_credit`: Credit account(s), comma/newline separated

### Environment Variables

All scripts support loading from `.env` file and command-line arguments. Key variables:
- `FREE_LOGIN`, `FREE_PASSWORD`: Free ISP credentials
- `FREE_MOBILE_LOGIN`, `FREE_MOBILE_PASSWORD`: Free Mobile credentials
- `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH`: Gmail OAuth credentials
- `SHEETS_SPREADSHEET_ID`, `SHEETS_RANGE`: Google Sheets config location
- `SHEETS_CREDENTIALS`, `SHEETS_TOKEN`: Sheets OAuth credentials
- `PAHEKO_BASE_URL`, `PAHEKO_USER`, `PAHEKO_PASS`: Paheko API credentials
- `FROM_DATE`: Default start date for invoice retrieval
- `OUTPUT_DIR`: Directory for downloaded invoices (default: `factures/`)
- `HEADLESS_MODE`: Run Selenium in headless mode (default: `true`)

## Docker Deployment

A local Paheko instance can be deployed using Docker Compose:

```bash
cd deploy
docker-compose up -d
```

This starts Paheko on `http://localhost:8080` using the official `paheko/paheko:1.3.15` image. Configuration is in `deploy/paheko/config.local.php` and data is persisted in a Docker volume.

## Important Patterns

### Date Handling
- Dates are parsed flexibly using `date_utils.parse_date_label_to_date()`
- Supports formats: `YYYY-MM-DD`, `YYYY-MM`, `MM/YYYY`, French month names like "Janvier 2024"
- All dates are normalized to `YYYY-MM-DD` format for Paheko

### Duplicate Prevention
Before creating a Paheko transaction, the runner checks the account journal for existing entries with the same date and label. If found, the export is skipped.

### Paheko Transaction Types
- **EXPENSE/REVENUE**: Simple 2-line transactions (amount + debit + credit)
- **TRANSFER**: Move funds between accounts
- **ADVANCED**: Multi-line transactions with custom lines array

### Selenium Usage
Free ISP invoice downloads use Selenium WebDriver in headless mode by default. Configure with `HEADLESS_MODE=false` to debug visually.

## API References

- **Paheko API**: https://paheko.cloud/api
- **Google Sheets API**: https://developers.google.com/sheets/api
- **Gmail API**: https://developers.google.com/gmail/api
