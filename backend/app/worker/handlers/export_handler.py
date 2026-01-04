"""Export handler for record export processing.

Handles records.export messages to:
1. Load record and exporter configuration
2. Transform record using mapper
3. Export to destination
4. Update record status
"""

import logging
from uuid import UUID

from faststream.nats import NatsMessage
from sqlmodel import Session, select

from app.core.db import engine
from app.core.logging import format_error_context, log_error_context
from app.core.vault import get_vault
from app.exports.gdrive import GDriveExporter
from app.exports.paheko import PahekoExporter
from app.mappers.record2gdrive import Record2GDriveMapper
from app.mappers.record2paheko import Record2PahekoMapper
from app.models import (
    Exporter,
    ExporterType,
    Mapper,
    Record,
    RecordStatus,
)
from app.worker.main import broker, records_stream

logger = logging.getLogger(__name__)


@broker.subscriber("records.export", stream=records_stream)
async def handle_record_export(data: dict, msg: NatsMessage) -> None:
    """Handle record export messages.

    Args:
        data: Export message data (record_id, workflow_id, exporter_ids)
        msg: NATS message for acknowledgment
    """
    record_id = UUID(data["record_id"])
    workflow_id = UUID(data["workflow_id"])
    exporter_ids = [UUID(eid) for eid in data.get("exporter_ids", [])]

    logger.info(f"Exporting record {record_id} to {len(exporter_ids)} exporters")

    try:
        # Load record
        with Session(engine) as session:
            record = session.get(Record, record_id)
            if not record:
                raise ValueError(f"Record {record_id} not found")

            # Update status to processing
            record.status = RecordStatus.processing
            session.add(record)
            session.commit()

        # Process each exporter
        success_count = 0
        error_count = 0
        errors = []

        for exporter_id in exporter_ids:
            try:
                exported = await _process_exporter(record_id, exporter_id)
                if exported:
                    success_count += 1
            except Exception as e:
                error_count += 1
                error_ctx = format_error_context(
                    error=e,
                    component="export_handler",
                    entity_id=exporter_id,
                    extra={"record_id": str(record_id)},
                )
                errors.append(error_ctx)
                logger.error(f"Export to {exporter_id} failed: {e}")

        # Update record status
        with Session(engine) as session:
            record = session.get(Record, record_id)
            if record:
                if error_count == 0:
                    record.status = RecordStatus.exported
                    record.error_context = None
                elif success_count > 0:
                    # Partial success
                    record.status = RecordStatus.exported
                    record.error_context = {"partial_errors": errors}
                else:
                    record.status = RecordStatus.failed
                    record.error_context = {"errors": errors}
                session.add(record)
                session.commit()

        logger.info(
            f"Record {record_id} export complete: "
            f"{success_count} success, {error_count} failed"
        )

        # Acknowledge message
        await msg.ack()

    except Exception as e:
        # Log with structured error context
        error_ctx = log_error_context(
            error=e,
            component="export_handler",
            entity_id=record_id,
            extra={"workflow_id": str(workflow_id), "exporter_count": len(exporter_ids)},
        )

        # Update record status to failed
        with Session(engine) as session:
            record = session.get(Record, record_id)
            if record:
                record.status = RecordStatus.failed
                record.error_context = error_ctx
                session.add(record)
                session.commit()

        # Negative ack to retry later
        await msg.nack()


async def _process_exporter(record_id: UUID, exporter_id: UUID) -> bool:
    """Process a single exporter for a record.

    Args:
        record_id: Record UUID
        exporter_id: Exporter UUID

    Returns:
        True if export succeeded, False if skipped
    """
    # Load exporter and mappers
    with Session(engine) as session:
        exporter = session.get(Exporter, exporter_id)
        if not exporter:
            raise ValueError(f"Exporter {exporter_id} not found")

        if not exporter.is_active:
            logger.debug(f"Exporter {exporter_id} is not active, skipping")
            return False

        # Get active mappers for this exporter
        mappers = session.exec(
            select(Mapper).where(
                Mapper.exporter_id == exporter_id,
                Mapper.is_active == True,  # noqa: E712
            )
        ).all()

        if not mappers:
            logger.warning(f"No active mappers for exporter {exporter_id}")
            return False

        # Load record
        record = session.get(Record, record_id)
        if not record:
            raise ValueError(f"Record {record_id} not found")

        # Store data for use outside session
        exporter_type = exporter.type
        exporter_config = exporter.config or {}

        mapper_data = [
            {
                "id": m.id,
                "transformation_logic": m.transformation_logic or {},
            }
            for m in mappers
        ]

        # Need to keep record in session scope for mapper
        # Detach by loading all needed data
        record_data = Record(
            id=record.id,
            source_id=record.source_id,
            workflow_id=record.workflow_id,
            date=record.date,
            data=record.data,
            file_path=record.file_path,
            file_hash=record.file_hash,
            unique_key=record.unique_key,
            status=record.status,
        )

    # Process based on exporter type
    if exporter_type == ExporterType.paheko:
        return await _export_to_paheko(
            record_data, exporter_id, exporter_config, mapper_data
        )
    elif exporter_type == ExporterType.gdrive:
        return await _export_to_gdrive(
            record_data, exporter_id, exporter_config, mapper_data
        )
    else:
        raise ValueError(f"Unsupported exporter type: {exporter_type}")


async def _export_to_paheko(
    record: Record,
    exporter_id: UUID,
    config: dict,
    mapper_data: list[dict],
) -> bool:
    """Export record to Paheko.

    Returns:
        True if exported, False if skipped (duplicate)
    """
    # Get credentials from Vault
    vault = get_vault()
    api_key = vault.get_paheko_api_key(str(exporter_id))

    # Create exporter
    exporter = PahekoExporter(config)
    exporter.api_key = api_key

    try:
        await exporter.connect()

        exported = False

        # Process each mapper
        for mdata in mapper_data:
            mapper = Record2PahekoMapper(
                exporter=exporter,
                rules=mdata["transformation_logic"],
            )
            result = await mapper.transform_and_export(record)
            if result:
                exported = True

        return exported

    finally:
        await exporter.disconnect()


async def _export_to_gdrive(
    record: Record,
    exporter_id: UUID,
    config: dict,
    mapper_data: list[dict],
) -> bool:
    """Export record to Google Drive.

    Returns:
        True if exported, False if skipped (duplicate or no file)
    """
    # Get credentials from Vault
    vault = get_vault()
    credentials = vault.get_gdrive_credentials(str(exporter_id))
    token = vault.get_gdrive_tokens(str(exporter_id))

    # Create exporter
    exporter = GDriveExporter(config)
    exporter.credentials = credentials
    exporter.token = token

    try:
        await exporter.connect()

        exported = False

        # Process each mapper
        for mdata in mapper_data:
            mapper = Record2GDriveMapper(
                exporter=exporter,
                rules=mdata["transformation_logic"],
            )
            result = await mapper.transform_and_export(record)
            if result:
                exported = True

        # Update token if refreshed
        if exporter.token != token:
            vault.store_gdrive_tokens(str(exporter_id), exporter.token)

        return exported

    finally:
        await exporter.disconnect()
