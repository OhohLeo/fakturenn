"""Job handler for source sync processing.

Handles jobs.trigger messages to:
1. Fetch data from sources
2. Parse into records
3. Store records in database
4. Trigger exports
"""

import logging
from datetime import datetime
from uuid import UUID

from faststream.nats import NatsMessage
from sqlmodel import Session, select

from app.core.db import engine
from app.core.logging import log_error_context
from app.core.nats import RecordExportMessage, get_nats
from app.core.storage import get_storage
from app.core.vault import get_vault
from app.models import (
    Exporter,
    Job,
    JobStatus,
    Parser,
    Record,
    RecordStatus,
    Source,
    SourceType,
)
from app.parsers.mail2record import Mail2RecordParser
from app.parsers.xls2record import XLS2RecordParser
from app.sources.gmail import GmailSource
from app.sources.xls import XLSSource
from app.worker.main import broker, jobs_stream

logger = logging.getLogger(__name__)


@broker.subscriber("jobs.trigger", stream=jobs_stream)
async def handle_job_trigger(data: dict, msg: NatsMessage) -> None:
    """Handle job trigger messages.

    Args:
        data: Job message data (job_id, source_id, workflow_id, triggered_at, triggered_by)
        msg: NATS message for acknowledgment
    """
    job_id = UUID(data["job_id"])
    source_id = UUID(data["source_id"])
    workflow_id = UUID(data["workflow_id"])
    triggered_by = data.get("triggered_by", "scheduler")

    logger.info(f"Processing job {job_id} for source {source_id}")

    try:
        # Update job status to running
        await _update_job_status(job_id, JobStatus.running)

        # Load source and parsers
        with Session(engine) as session:
            source = session.get(Source, source_id)
            if not source:
                raise ValueError(f"Source {source_id} not found")

            # Get active parsers for this source
            parsers = session.exec(
                select(Parser).where(
                    Parser.source_id == source_id,
                    Parser.is_active == True,  # noqa: E712
                )
            ).all()

            if not parsers:
                raise ValueError(f"No active parsers for source {source_id}")

            # Store source data for use outside session
            source_type = source.type
            source_config = source.config or {}
            source_name = source.name

            # Store parser data
            parser_data = [
                {
                    "id": p.id,
                    "engine_type": p.engine_type,
                    "rules": p.rules or {},
                }
                for p in parsers
            ]

        # Process based on source type
        records_created = 0

        if source_type == SourceType.gmail:
            records_created = await _process_gmail_source(
                source_id, workflow_id, source_config, parser_data
            )
        elif source_type == SourceType.xls:
            records_created = await _process_xls_source(
                source_id, workflow_id, source_config, parser_data
            )
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

        # Update job status to success
        await _update_job_status(job_id, JobStatus.success)

        # Update source last_sync_at
        with Session(engine) as session:
            source = session.get(Source, source_id)
            if source:
                source.last_sync_at = datetime.utcnow()
                source.error_context = None
                session.add(source)
                session.commit()

        logger.info(
            f"Job {job_id} completed: {records_created} records created"
        )

        # Acknowledge message
        await msg.ack()

    except Exception as e:
        # Log with structured error context
        error_ctx = log_error_context(
            error=e,
            component="job_handler",
            entity_id=job_id,
            extra={
                "source_id": str(source_id),
                "workflow_id": str(workflow_id),
                "triggered_by": triggered_by,
            },
        )

        # Update job status to failed
        await _update_job_status(job_id, JobStatus.failed, error_context=error_ctx)

        # Update source error_context
        with Session(engine) as session:
            source = session.get(Source, source_id)
            if source:
                source.error_context = error_ctx
                session.add(source)
                session.commit()

        # Negative ack to retry later
        await msg.nack()


async def _update_job_status(
    job_id: UUID,
    status: JobStatus,
    error_context: dict | None = None,
) -> None:
    """Update job status in database."""
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job:
            job.status = status
            if status == JobStatus.running:
                job.started_at = datetime.utcnow()
            if error_context:
                job.error_context = error_context
            session.add(job)
            session.commit()


async def _process_gmail_source(
    source_id: UUID,
    workflow_id: UUID,
    config: dict,
    parser_data: list[dict],
) -> int:
    """Process Gmail source with Mail2Record parser.

    Returns:
        Number of records created
    """
    # Get credentials from Vault
    vault = get_vault()
    credentials = vault.get_gmail_credentials(str(source_id))
    token = vault.get_gmail_tokens(str(source_id))

    # Create Gmail source
    source = GmailSource(config)
    source.credentials = credentials
    source.token = token

    try:
        await source.connect()

        records_created = 0

        # Process each parser
        for pdata in parser_data:
            parser = Mail2RecordParser(source=source, rules=pdata["rules"])
            parsed_records = await parser.parse()

            for parsed in parsed_records:
                record_id = await _create_record(
                    source_id=source_id,
                    workflow_id=workflow_id,
                    parsed_record=parsed,
                )
                if record_id:
                    records_created += 1
                    # Trigger export
                    await _trigger_export(record_id, workflow_id)

        # Update token if refreshed
        if source.token != token:
            vault.store_gmail_tokens(str(source_id), source.token)

        return records_created

    finally:
        await source.disconnect()


async def _process_xls_source(
    source_id: UUID,
    workflow_id: UUID,
    config: dict,
    parser_data: list[dict],
) -> int:
    """Process XLS source with XLS2Record parser.

    Returns:
        Number of records created
    """
    # Create XLS source
    source = XLSSource(config)

    try:
        await source.connect()

        records_created = 0

        # Process each parser
        for pdata in parser_data:
            parser = XLS2RecordParser(source=source, rules=pdata["rules"])
            parsed_records = await parser.parse()

            for parsed in parsed_records:
                record_id = await _create_record(
                    source_id=source_id,
                    workflow_id=workflow_id,
                    parsed_record=parsed,
                )
                if record_id:
                    records_created += 1
                    # Trigger export
                    await _trigger_export(record_id, workflow_id)

        return records_created

    finally:
        await source.disconnect()


async def _create_record(
    source_id: UUID,
    workflow_id: UUID,
    parsed_record: dict,
) -> UUID | None:
    """Create a Record from parsed data.

    Handles duplicate detection via unique_key.

    Returns:
        Record UUID if created, None if duplicate
    """
    from app.models import Record

    # Compute unique key
    unique_key = Record.compute_unique_key(
        source_id=source_id,
        date=parsed_record.record_date,
        file_content=parsed_record.file_content,
        data=parsed_record.data,
    )

    # Check for duplicate
    with Session(engine) as session:
        existing = session.exec(
            select(Record).where(Record.unique_key == unique_key)
        ).first()

        if existing:
            logger.debug(f"Skipping duplicate record: {unique_key}")
            return None

    # Upload file if present
    file_path = None
    file_hash = None

    if parsed_record.file_content and parsed_record.file_name:
        storage = get_storage()
        file_path, file_hash = storage.upload_file(
            workflow_id=workflow_id,
            date=parsed_record.record_date,
            source_type="record",
            invoice_id=parsed_record.source_item_id or "unknown",
            content=parsed_record.file_content,
        )

    # Create record
    with Session(engine) as session:
        record = Record(
            source_id=source_id,
            workflow_id=workflow_id,
            date=parsed_record.record_date,
            data=parsed_record.data,
            file_path=file_path,
            file_hash=file_hash,
            unique_key=unique_key,
            status=RecordStatus.pending,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        logger.info(f"Created record {record.id}")
        return record.id


async def _trigger_export(record_id: UUID, workflow_id: UUID) -> None:
    """Trigger export for a record.

    Publishes export message for all active exporters.
    """
    # Get active exporters for workflow
    with Session(engine) as session:
        exporters = session.exec(
            select(Exporter).where(
                Exporter.workflow_id == workflow_id,
                Exporter.is_active == True,  # noqa: E712
            )
        ).all()

        exporter_ids = [e.id for e in exporters]

    if not exporter_ids:
        logger.debug(f"No active exporters for workflow {workflow_id}")
        return

    # Publish export message
    nats = await get_nats()
    message = RecordExportMessage(
        record_id=record_id,
        workflow_id=workflow_id,
        exporter_ids=exporter_ids,
    )
    await nats.publish_record_export(message)

    logger.debug(f"Triggered export for record {record_id}")
