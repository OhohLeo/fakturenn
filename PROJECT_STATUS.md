# Treasury Data Extraction System - Project Status

## Overview

This project extends the full-stack-fastapi-template into an event-driven Treasury Data Extraction system. It automates invoice data extraction from various sources (Gmail, Excel) and exports to accounting systems (Paheko) and file storage (Google Drive).

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Sources   │────▶│   Parsers   │────▶│   Records   │
│ Gmail, XLS  │     │ Mail2Record │     │  Database   │
└─────────────┘     │ XLS2Record  │     └──────┬──────┘
                    └─────────────┘            │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Exporters  │◀────│   Mappers   │◀────│   Workers   │
│Paheko,GDrive│     │Record2Paheko│     │ FastStream  │
└─────────────┘     │Record2GDrive│     └─────────────┘
                    └─────────────┘
```

## Tech Stack

- **Backend**: FastAPI + SQLModel + PostgreSQL
- **Message Queue**: NATS JetStream
- **Worker**: FastStream
- **Scheduler**: APScheduler
- **File Storage**: MinIO (S3-compatible)
- **Secrets**: HashiCorp Vault
- **Frontend**: React + TanStack Router + shadcn/ui

## Implementation Status

### Phase 1: Core Foundation ✅

- [x] Database models (Workflow, Source, Parser, Record, Exporter, Mapper, Job)
- [x] Alembic migration for all tables
- [x] CRUD functions for all models
- [x] API routes (workflows, sources, exporters, records, jobs, schemas)
- [x] SDUI schema registry with JSON Schema validation
- [x] MinIO storage client
- [x] Vault client for secrets management
- [x] Docker-compose with nats, vault, minio services

### Phase 2: Source & Export Pipeline ✅

- [x] Base source class and models
- [x] GmailSource - Gmail API connectivity
- [x] XLSSource - Excel spreadsheet reader
- [x] Base parser class
- [x] Mail2RecordParser - Gmail to Record conversion
- [x] XLS2RecordParser - Excel to Record conversion
- [x] Base exporter class
- [x] PahekoExporter - Paheko accounting API client
- [x] GDriveExporter - Google Drive API client
- [x] Base mapper class
- [x] Record2PahekoMapper - Record to Paheko transaction
- [x] Record2GDriveMapper - Record to GDrive file upload

### Phase 3: Async Infrastructure ✅

- [x] NATS client with message schemas
- [x] Scheduler service (APScheduler)
- [x] FastStream worker application
- [x] Job handler (source sync processing)
- [x] Export handler (record export processing)
- [x] Worker Dockerfile
- [x] Docker-compose worker service

### Phase 4: Testing & Polish ✅

- [x] Backend tests for API routes
- [x] Backend tests for sources/parsers
- [x] Backend tests for exports/mappers
- [x] Structured error logging utility
- [x] Error context tracking in workers
- [x] PROJECT_STATUS.md documentation

### Phase 5: Frontend (Pending)

- [ ] Workflow management pages
- [ ] Source/Parser configuration with SDUI forms
- [ ] Exporter/Mapper configuration
- [ ] Record list and detail views
- [ ] Job history and status views
- [ ] DynamicForm component with AJV validation

## Directory Structure

```
backend/
├── app/
│   ├── api/routes/          # API endpoints
│   │   ├── workflows.py
│   │   ├── sources.py
│   │   ├── exporters.py
│   │   ├── records.py
│   │   ├── jobs.py
│   │   └── schemas.py
│   ├── core/
│   │   ├── config.py        # Settings
│   │   ├── db.py            # Database
│   │   ├── nats.py          # NATS client
│   │   ├── vault.py         # Vault client
│   │   ├── storage.py       # MinIO client
│   │   └── logging.py       # Error logging
│   │   └── schemas/         # JSON Schema registry
│   ├── sources/             # Source implementations
│   │   ├── gmail.py
│   │   └── xls.py
│   ├── parsers/             # Parser implementations
│   │   ├── mail2record.py
│   │   └── xls2record.py
│   ├── exports/             # Exporter implementations
│   │   ├── paheko.py
│   │   └── gdrive.py
│   ├── mappers/             # Mapper implementations
│   │   ├── record2paheko.py
│   │   └── record2gdrive.py
│   ├── scheduler/           # APScheduler service
│   │   └── service.py
│   ├── worker/              # FastStream worker
│   │   ├── main.py
│   │   └── handlers/
│   │       ├── job_handler.py
│   │       └── export_handler.py
│   └── models.py            # Database models
├── tests/
│   ├── api/routes/          # Route tests
│   ├── sources/             # Source tests
│   ├── parsers/             # Parser tests
│   ├── exports/             # Exporter tests
│   └── mappers/             # Mapper tests
└── Dockerfile.worker        # Worker container
```

## Database Models

| Model | Description |
|-------|-------------|
| Workflow | User's workflow container |
| Source | Data source (gmail, xls) |
| Parser | Source parser (mail2record, xls2record) |
| Record | Extracted invoice record |
| Exporter | Export destination (paheko, gdrive) |
| Mapper | Record transformation rules |
| Job | Sync job execution record |

## Message Flow

1. **Scheduler** triggers job based on Source crontab
2. **Job** message published to NATS `jobs.trigger`
3. **Worker** processes job:
   - Connects to Source
   - Runs Parser to create Records
   - Publishes export messages
4. **Export** message published to NATS `records.export`
5. **Worker** processes export:
   - Runs Mapper transformation
   - Exports via Exporter

## Configuration

### Environment Variables

```bash
# NATS
NATS_URL=nats://nats:4222

# Vault
VAULT_URL=http://vault:8200
VAULT_TOKEN=dev-token

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=fakturenn-invoices
```

### Running the Stack

```bash
# Start all services
docker compose watch

# View logs
docker compose logs -f worker

# Run tests
docker compose exec backend bash scripts/tests-start.sh
```

## Next Steps

1. **Frontend Implementation**: Build React UI for workflow management
2. **OAuth Flow**: Implement Gmail/GDrive OAuth consent flow
3. **Monitoring**: Add Prometheus metrics and Grafana dashboards
4. **Production Vault**: Configure proper Vault authentication
5. **Additional Sources**: Add Free/FreeMobile invoice sources (Selenium)
