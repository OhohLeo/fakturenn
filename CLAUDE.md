# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Fakturenn** is a production-ready automation suite for managing invoicing for a micro-crèche (Youn Ha Solena). It provides a REST API with multi-tenant support to retrieve invoices from various sources (Free, Free Mobile, Gmail), extract relevant data, and export to multiple destinations (Paheko accounting, local filesystem, Google Drive).

**Technology Stack**: Python 3.12+, uv (package manager), FastAPI, PostgreSQL, NATS JetStream, Vault, Docker, Selenium (for web scraping), Google APIs

## Development Commands

### Environment Setup
```bash
# Install dependencies with uv
uv sync

# Load environment variables from .env file
# The project looks for .env with credentials:
# VAULT_ADDR, VAULT_ROLE_ID, VAULT_SECRET_ID (Vault setup)
# DATABASE_URL (PostgreSQL connection)
# NATS_SERVERS (NATS server URLs)
# FREE_LOGIN, FREE_PASSWORD, FREE_MOBILE_LOGIN, FREE_MOBILE_PASSWORD
# GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
```

### Running Services

```bash
# Start all services with Docker Compose
docker-compose -f deploy/docker-compose.yml up -d

# Run API server
uv run python -m uvicorn app.api.main:app --reload

# Run job coordinator worker
uv run python scripts/run_job_coordinator.py

# Run source worker
uv run python scripts/run_source_worker.py

# Run export worker
uv run python scripts/run_export_worker.py

# Database migrations
uv run alembic upgrade head
uv run alembic downgrade -1
```

### Code Quality
```bash
# Lint and format with ruff
uv run ruff format .
uv run ruff check .

# Run tests
uv run pytest tests/ -v
uv run pytest tests/ --cov=app  # with coverage
```

## Architecture

### Multi-Service Event-Driven Architecture

Fakturenn uses an event-driven microservices architecture with REST API frontend and async workers:

```
User/Client
    ↓
FastAPI REST API (app/api/)
    ↓ (triggers job)
NATS JetStream (message broker)
    ↓
Job Coordinator Worker
    ├→ Source Worker (concurrent)
    │  └→ invokes app/sources/
    └→ Export Worker (concurrent)
       └→ invokes app/export/
    ↓
PostgreSQL (state persistence)
    ↓
External Systems (Paheko, Google Drive, Local FS)
```

### Core Flow

1. **User creates automation** via REST API (`POST /automations`)
   - Configure sources (FreeInvoice, FreeMobileInvoice, Gmail)
   - Configure exports (Paheko, LocalStorage, GoogleDrive)
   - Define source-export mappings (many-to-many)

2. **User triggers job** via REST API (`POST /automations/{id}/trigger`)
   - REST endpoint creates Job in database
   - Publishes `JobStartedEvent` to NATS

3. **Job Coordinator Worker** (`app/workers/job_coordinator.py`)
   - Subscribes to JobStartedEvent
   - Loads automation and all active sources
   - Publishes SourceExecuteEvent for each source
   - Tracks job progress and publishes JobCompletedEvent/JobFailedEvent

4. **Source Worker** (`app/workers/source_worker.py` - in progress)
   - Subscribes to SourceExecuteEvent
   - Executes source-specific extraction (Free/FreeMobile/Gmail)
   - Downloads PDF and extracts metadata
   - Publishes ExportExecuteEvent for mapped exports

5. **Export Worker** (`app/workers/export_worker.py` - in progress)
   - Subscribes to ExportExecuteEvent
   - Executes export handler (Paheko/LocalStorage/GoogleDrive)
   - Publishes ExportCompletedEvent/ExportFailedEvent
   - Stores export history and external reference

### Key Components

#### API (`app/api/`)
- **`main.py`**: FastAPI application factory with lifecycle hooks
- **`auth.py`**: JWT token generation/validation with refresh tokens
- **`dependencies.py`**: Dependency injection (DB session, current user, admin check, Vault client)
- **`routers/`**: API endpoints for users, automations, sources, exports, mappings, jobs, health
- **`schemas/`**: Pydantic models for request/response validation

#### Database (`app/db/`)
- **`models.py`**: SQLAlchemy ORM models (User, Automation, Source, Export, SourceExportMapping, Job, ExportHistory, AuditLog)
- **`connection.py`**: Async connection manager with session factory
- **Alembic migrations**: Schema versioning under `migrations/`

#### NATS (`app/nats/`)
- **`client.py`**: NatsClientWrapper with JetStream support, stream/consumer management
- **`messages.py`**: Pydantic event schemas (JobStartedEvent, SourceExecuteEvent, ExportExecuteEvent, etc.)

#### Export Handlers (`app/export/`)
- **`base.py`**: Abstract ExportHandler interface and factory function
- **`paheko_handler.py`**: Paheko accounting integration with duplicate detection
- **`local_storage.py`**: Filesystem organization with configurable path templates
- **`google_drive.py`**: Google Drive backup integration (OAuth hooks)

#### Core (`app/core/`)
- **`vault_client.py`**: Vault client with AppRole authentication and token auto-renewal
- **`path_template.py`**: Path template rendering system with French month names
  - Supports variables: `{year}`, `{month}`, `{month_name}`, `{quarter}`, `{date}`, `{invoice_id}`, `{source}`, `{amount}`
  - Example: `"{year}/{month_name}/[{source}] {invoice_id}.pdf"` → `"2025/Octobre/[Free] INV-001.pdf"`
- **`logging_config.py`**: Structured JSON logging configuration

#### Workers (`app/workers/`)
- **`job_coordinator.py`**: Orchestrates job execution and tracks progress
- **`source_worker.py`**: (in progress) Executes source extraction and publishes export events
- **`export_worker.py`**: (in progress) Executes export handlers and publishes completion events

#### Sources (`app/sources/`)
- **`invoice.py`**: `Invoice` dataclass - universal representation
- **`free.py`**: Free ISP invoice scraper (Selenium)
- **`free_mobile.py`**: Free Mobile invoice extractor (Gmail)
- **`gmail_manager.py`**: Gmail API wrapper
- **`runner.py`**: Source executor with extraction logic

### Data Flow Example

1. User creates automation with source (Gmail) and exports (Paheko + LocalStorage)
2. User triggers job via `POST /automations/1/trigger`
3. API creates Job and publishes JobStartedEvent
4. Job Coordinator receives event, fetches automation/sources, publishes SourceExecuteEvent
5. Source Worker receives event, extracts invoices from Gmail, publishes ExportExecuteEvent
6. Export Worker receives event twice (for Paheko and LocalStorage), exports PDFs
7. Workers publish ExportCompletedEvent for each, Coordinator aggregates and publishes JobCompletedEvent
8. Job status updated to "completed", export history recorded with external references

## Configuration

### API-Based Configuration

Configuration is now managed through REST API endpoints:

1. **Create User** (`POST /auth/register`)
   - Username and password for authentication
   - Language (fr/en) and timezone preferences

2. **Create Automation** (`POST /automations`)
   - Name and description
   - Active status
   - Schedule (cron expression, optional)
   - From-date rule (optional)

3. **Create Sources** (`POST /sources`)
   - Assign to automation
   - Type: `FreeInvoice`, `FreeMobileInvoice`, or `Gmail`
   - For Gmail: email_sender_from, email_subject_contains
   - Extraction params (JSON): regex patterns, extraction logic
   - Max results per execution (default 30)

4. **Create Exports** (`POST /exports`)
   - Assign to automation
   - Type: `Paheko`, `LocalStorage`, or `GoogleDrive`
   - Configuration (JSON):
     - **Paheko**: `paheko_type`, `label_template`, `debit`, `credit`, `base_url`
     - **LocalStorage**: `base_path`, `path_template`, `create_directories`
     - **GoogleDrive**: `folder_id`, `name_template`

5. **Create Mappings** (`POST /mappings`)
   - Connect sources to exports (many-to-many)
   - Priority (execution order)
   - Conditions (JSON, optional filtering)

### Path Template Variables

LocalStorage exports support flexible path organization via template variables:

```
{year}          → 2025
{month}         → 10 (zero-padded)
{month_name}    → Octobre (French name)
{quarter}       → Q4
{date}          → 2025-10-29
{invoice_id}    → INV-001
{source}        → Free
{amount}        → 99.99
{filename}      → facture.pdf
```

Example templates:
- `{year}/{month}/{filename}` → `2025/10/facture.pdf`
- `{year}/{month_name}/{source}_{invoice_id}.pdf` → `2025/Octobre/Free_INV-001.pdf`
- `{year}/Q{quarter}/{invoice_id}.pdf` → `2025/Q4/INV-001.pdf`

### Environment Variables

Key variables loaded from `.env`:

**Infrastructure**:
- `VAULT_ADDR`: HashiCorp Vault address (e.g., `http://localhost:8200`)
- `VAULT_ROLE_ID`: AppRole role ID
- `VAULT_SECRET_ID`: AppRole secret ID
- `DATABASE_URL`: PostgreSQL connection (e.g., `postgresql+asyncpg://user:pass@localhost/dbname`)
- `NATS_SERVERS`: Comma-separated NATS URLs (e.g., `nats://localhost:4222`)

**API**:
- `JWT_SECRET_KEY`: Secret for JWT signing
- `JWT_ALGORITHM`: Algorithm for JWT (default: HS256)
- `JWT_EXPIRATION_HOURS`: Access token lifetime (default: 1)

**Services** (stored in Vault secret/data/fakturenn/):
- Free ISP: `free_login`, `free_password`
- Free Mobile: `free_mobile_login`, `free_mobile_password`
- Gmail: `gmail_credentials`, `gmail_token`
- Paheko: `base_url`, `username`, `password`

## Docker Deployment

Complete stack deployment with 8 services:

```bash
cd deploy
docker-compose up -d
```

### Services

1. **PostgreSQL 16** (`postgres:16-alpine`)
   - Port: `5432`
   - Database: `fakturenn`
   - Volume: `postgres_data`

2. **HashiCorp Vault 1.15** (`vault:1.15`)
   - Port: `8200`
   - Backend: File storage in `vault_data`
   - Dev mode initialization with AppRole

3. **NATS 2.10 with JetStream** (`nats:2.10`)
   - Port: `4222` (NATS)
   - Port: `8222` (Management UI)
   - JetStream enabled by default

4. **FastAPI Application** (`Dockerfile.api`)
   - Port: `8000`
   - Health check on `GET /health`
   - Depends on PostgreSQL, Vault, NATS

5. **Job Coordinator Worker** (`Dockerfile.worker`)
   - Subscribes to `job.started` events
   - Orchestrates source and export workers

6. **Source Worker** (`Dockerfile.worker`)
   - Subscribes to `source.execute` events
   - Executes source extraction logic
   - Includes Chromium/ChromeDriver for Selenium

7. **Export Worker** (`Dockerfile.worker`)
   - Subscribes to `export.execute` events
   - Executes export handlers

8. **Paheko 1.3.16** (`paheko/paheko:1.3.16`)
   - Port: `8080`
   - Configuration: `deploy/paheko/config.local.php`
   - Database: PostgreSQL via docker-compose

### Health Checks

All services include health checks:
- PostgreSQL: TCP port check
- Vault: HTTP status endpoint
- NATS: TCP port check
- API: HTTP GET /health
- Workers: NATS connectivity check

## Important Patterns

### Multi-Tenancy
- Every resource (automation, source, export, job) belongs to a User
- API endpoints automatically filter by `current_user.id`
- Database foreign keys enforce user isolation
- AuditLog tracks user actions for compliance

### JWT Authentication
- Tokens issued on login with exp claim
- Access tokens valid for configurable period (default 1 hour)
- Refresh tokens for extending session
- Bearer token in `Authorization: Bearer <token>` header

### Event-Driven Messaging
- Jobs are async and state is tracked in database
- Events published to NATS JetStream for durability
- Workers subscribe with durable consumers (auto-restart after failure)
- Negative acknowledgment (nak) triggers message replay

### Paheko Duplicate Detection
- Before creating transaction, checks account journal
- Matches on date AND label to prevent duplicates
- Skipped duplicates logged as `duplicate_skipped` status
- Enables safe job re-runs

### Paheko Transaction Types
- **EXPENSE/REVENUE**: Simple 2-line transactions (amount + debit + credit)
- **TRANSFER**: Move funds between accounts
- **ADVANCED**: Multi-line transactions with custom lines array

### Path Templating
- LocalStorage handler uses `path_template.render_path_template()`
- Variables interpolated from invoice data and context
- French month names via lookup table
- Validation ensures all required variables present

### Vault Secrets Management
- Credentials stored in `secret/data/fakturenn/<service>`
- AppRole authentication with role_id/secret_id
- Automatic token renewal before expiration
- Thread-safe with lock-protected state

### Selenium Web Scraping
- Free ISP invoice downloads require browser automation
- Headless mode by default for server environments
- Chrome/Chromium required (included in worker Docker image)
- Timeouts and error handling for network failures

## Database Schema

### Core Tables
- **users**: Multi-tenant users with language/timezone
- **automations**: Automation orchestrations per user
- **sources**: Invoice sources (FreeInvoice, FreeMobileInvoice, Gmail)
- **exports**: Export destinations (Paheko, LocalStorage, GoogleDrive)
- **source_export_mappings**: Many-to-many with priority and conditions
- **jobs**: Job execution tracking with status and stats
- **export_history**: Audit trail with external references
- **audit_log**: User action tracking for compliance

### Indexes
- User-scoped queries: `idx_automations_user`, `idx_sources_automation`, `idx_exports_automation`
- Status queries: `idx_jobs_status`, `idx_export_history_status`
- Lookups: Unique constraints on `(user_id, automation_name)`, `(source_id, export_id)`

## API References

- **API Documentation**: `GET /docs` (Swagger UI) or `GET/openapi.json` (OpenAPI schema)
- **Paheko API**: https://paheko.cloud/api
- **NATS**: https://docs.nats.io/
- **FastAPI**: https://fastapi.tiangolo.com/
- **SQLAlchemy**: https://sqlalchemy.org/