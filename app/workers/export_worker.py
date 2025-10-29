"""Export worker for executing export handlers."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_manager
from app.db.models import Export, ExportHistory
from app.export.base import get_export_handler
from app.nats import (
    NatsClient,
    ExportExecuteEvent,
    ExportCompletedEvent,
    ExportFailedEvent,
)

logger = logging.getLogger(__name__)


class ExportWorker:
    """Executes export handlers and tracks results."""

    def __init__(self, nats_client: NatsClient):
        """Initialize export worker.

        Args:
            nats_client: NATS client for messaging
        """
        self.nats = nats_client
        self.db_manager = get_db_manager()

    async def start(self) -> None:
        """Start the export worker."""
        # Set up NATS streams and consumers
        await self.nats.ensure_stream(
            "export_events",
            ["export.execute"],
        )

        await self.nats.ensure_consumer(
            "export_events",
            "export_worker_consumer",
            "export.execute",
        )

        # Subscribe to export execute events
        async def handle_export_execute(data: dict):
            event = ExportExecuteEvent(**data)
            await self.handle_export_execute(event)

        await self.nats.subscribe_jetstream(
            "export_events",
            "export_worker_consumer",
            handle_export_execute,
        )

        logger.info("Export worker started")

    async def handle_export_execute(self, event: ExportExecuteEvent) -> None:
        """Handle export execute event.

        Args:
            event: ExportExecuteEvent message
        """
        job_id = event.job_id
        automation_id = event.automation_id
        user_id = event.user_id
        export_ids = event.export_ids
        invoice_data = event.invoice_data
        context = event.context

        logger.info(f"Processing export(s) {export_ids} for job {job_id}")

        # Execute each export
        for export_id in export_ids:
            try:
                # Get export configuration from database
                async with self.db_manager.get_session() as session:
                    export = await self._get_export(session, export_id, automation_id)
                    if not export:
                        raise ValueError(f"Export {export_id} not found")

                    # Execute export handler
                    handler = get_export_handler(export.type, export.configuration)
                    result = await handler.export(invoice_data, context)

                    # Create export history record
                    await self._create_export_history(
                        session,
                        job_id,
                        export_id,
                        export.type,
                        result.status,
                        context,
                        result.external_reference,
                        result.error_message,
                    )

                # Publish completion/failure event
                if result.status == "success":
                    event_data = ExportCompletedEvent(
                        job_id=job_id,
                        export_id=export_id,
                        automation_id=automation_id,
                        user_id=user_id,
                        external_reference=result.external_reference or "",
                        export_type=export.type,
                    )
                    await self.nats.publish(
                        "export.completed",
                        event_data.model_dump(mode="json"),
                    )
                    logger.info(
                        f"Export {export_id} completed "
                        f"(ref: {result.external_reference})",
                    )
                elif result.status == "duplicate_skipped":
                    # Log as completion but note it was a duplicate
                    event_data = ExportCompletedEvent(
                        job_id=job_id,
                        export_id=export_id,
                        automation_id=automation_id,
                        user_id=user_id,
                        external_reference="duplicate",
                        export_type=export.type,
                    )
                    await self.nats.publish(
                        "export.completed",
                        event_data.model_dump(mode="json"),
                    )
                    logger.info(f"Export {export_id} skipped (duplicate)")
                else:
                    # Failure
                    event_data = ExportFailedEvent(
                        job_id=job_id,
                        export_id=export_id,
                        automation_id=automation_id,
                        user_id=user_id,
                        error_message=result.error_message or "Export failed",
                        export_type=export.type,
                    )
                    await self.nats.publish(
                        "export.failed",
                        event_data.model_dump(mode="json"),
                    )
                    logger.error(
                        f"Export {export_id} failed: {result.error_message}",
                    )

            except Exception as e:
                logger.error(
                    f"Failed to execute export {export_id}: {e}",
                    exc_info=True,
                )

                # Publish failure event
                try:
                    event_data = ExportFailedEvent(
                        job_id=job_id,
                        export_id=export_id,
                        automation_id=automation_id,
                        user_id=user_id,
                        error_message=str(e),
                        export_type="Unknown",
                    )
                    await self.nats.publish(
                        "export.failed",
                        event_data.model_dump(mode="json"),
                    )
                except Exception as publish_error:
                    logger.error(
                        f"Failed to publish export failure event: {publish_error}",
                    )

    async def _get_export(
        self,
        session: AsyncSession,
        export_id: int,
        automation_id: int,
    ) -> Optional[Export]:
        """Get export by ID.

        Args:
            session: Database session
            export_id: Export ID
            automation_id: Automation ID (for verification)

        Returns:
            Export object or None
        """
        stmt = select(Export).where(
            Export.id == export_id,
            Export.automation_id == automation_id,
            Export.active.is_(True),
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _create_export_history(
        self,
        session: AsyncSession,
        job_id: int,
        export_id: int,
        export_type: str,
        status: str,
        context: Dict,
        external_reference: Optional[str],
        error_message: Optional[str],
    ) -> None:
        """Create export history record.

        Args:
            session: Database session
            job_id: Job ID
            export_id: Export ID
            export_type: Export type
            status: Export status
            context: Export context
            external_reference: Reference from external system
            error_message: Error message if failed
        """
        try:
            history = ExportHistory(
                job_id=job_id,
                export_id=export_id,
                export_type=export_type,
                status=status,
                exported_at=datetime.utcnow(),
                error_message=error_message,
                context=context,
                external_reference=external_reference,
            )
            session.add(history)
            await session.commit()
            logger.debug(f"Created export history record for export {export_id}")
        except Exception as e:
            logger.error(f"Failed to create export history: {e}", exc_info=True)
            await session.rollback()


async def run_export_worker(
    nats_servers: List[str],
    db_url: str,
) -> None:
    """Run export worker.

    Args:
        nats_servers: List of NATS server URLs
        db_url: Database connection URL
    """
    # Initialize dependencies
    from app.nats import init_nats_client, close_nats_client
    from app.db.connection import init_db_manager

    # Initialize database
    init_db_manager(db_url)

    # Initialize NATS
    nats_client = await init_nats_client(nats_servers)

    try:
        # Create and start worker
        worker = ExportWorker(nats_client)
        await worker.start()

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Export worker shutting down")
    except Exception as e:
        logger.error(f"Export worker error: {e}", exc_info=True)
    finally:
        await close_nats_client()
