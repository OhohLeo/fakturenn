"""Source worker for executing invoice source extraction."""

import asyncio
import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_manager
from app.db.models import Source, SourceExportMapping
from app.nats import (
    NatsClient,
    SourceExecuteEvent,
    ExportExecuteEvent,
)
from app.sources.invoice import Invoice
from app.sources.runner import SourceRunner

logger = logging.getLogger(__name__)


class SourceWorker:
    """Executes source extraction and publishes export events."""

    def __init__(self, nats_client: NatsClient):
        """Initialize source worker.

        Args:
            nats_client: NATS client for messaging
        """
        self.nats = nats_client
        self.db_manager = get_db_manager()
        self.source_runner = SourceRunner()

    async def start(self) -> None:
        """Start the source worker."""
        # Set up NATS streams and consumers
        await self.nats.ensure_stream(
            "source_events",
            ["source.execute"],
        )

        await self.nats.ensure_consumer(
            "source_events",
            "source_worker_consumer",
            "source.execute",
        )

        # Subscribe to source execute events
        async def handle_source_execute(data: dict):
            event = SourceExecuteEvent(**data)
            await self.handle_source_execute(event)

        await self.nats.subscribe_jetstream(
            "source_events",
            "source_worker_consumer",
            handle_source_execute,
        )

        logger.info("Source worker started")

    async def handle_source_execute(self, event: SourceExecuteEvent) -> None:
        """Handle source execute event.

        Args:
            event: SourceExecuteEvent message
        """
        job_id = event.job_id
        automation_id = event.automation_id
        user_id = event.user_id
        source_id = event.source_id

        logger.info(
            f"Executing source {source_id} (type: {event.source_type}) for job {job_id}",
        )

        try:
            # Get source configuration from database
            async with self.db_manager.get_session() as session:
                source = await self._get_source(session, source_id, automation_id)
                if not source:
                    raise ValueError(f"Source {source_id} not found")

                # Get export mappings for this source
                export_mappings = await self._get_export_mappings(
                    session,
                    source_id,
                )

            if not export_mappings:
                logger.warning(f"No export mappings found for source {source_id}")
                return

            # Execute source extraction
            invoices = await self._extract_invoices(
                source,
                event,
            )

            logger.info(f"Extracted {len(invoices)} invoices from source {source_id}")

            # Publish export events for each invoice and mapped export
            for invoice in invoices:
                for mapping in export_mappings:
                    export_id = mapping.export_id

                    # Build invoice data
                    invoice_data = {
                        "file_path": str(invoice.file_path),
                        "amount_eur": float(invoice.amount) if invoice.amount else None,
                    }

                    # Build context
                    context = {
                        "invoice_id": invoice.invoice_id,
                        "date": invoice.date if invoice.date else "",
                        "amount_eur": float(invoice.amount) if invoice.amount else 0.0,
                        "month": invoice.date.split("-")[1] if invoice.date else "",
                        "year": invoice.date.split("-")[0] if invoice.date else "",
                        "source": event.source_name,
                    }

                    # Create export event
                    export_event = ExportExecuteEvent(
                        job_id=job_id,
                        automation_id=automation_id,
                        user_id=user_id,
                        source_id=source_id,
                        export_ids=[export_id],
                        invoice_data=invoice_data,
                        context=context,
                    )

                    await self.nats.publish(
                        "export.execute",
                        export_event.model_dump(mode="json"),
                    )

                    logger.info(
                        f"Published export event for invoice {invoice.invoice_id} "
                        f"to export {export_id}",
                    )

        except Exception as e:
            logger.error(
                f"Failed to execute source {source_id}: {e}",
                exc_info=True,
            )

    async def _get_source(
        self,
        session: AsyncSession,
        source_id: int,
        automation_id: int,
    ) -> Optional[Source]:
        """Get source by ID.

        Args:
            session: Database session
            source_id: Source ID
            automation_id: Automation ID (for verification)

        Returns:
            Source object or None
        """
        stmt = select(Source).where(
            Source.id == source_id,
            Source.automation_id == automation_id,
            Source.active.is_(True),
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_export_mappings(
        self,
        session: AsyncSession,
        source_id: int,
    ) -> List[SourceExportMapping]:
        """Get export mappings for source.

        Args:
            session: Database session
            source_id: Source ID

        Returns:
            List of export mappings
        """
        stmt = select(SourceExportMapping).where(
            SourceExportMapping.source_id == source_id,
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def _extract_invoices(
        self,
        source: Source,
        event: SourceExecuteEvent,
    ) -> List[Invoice]:
        """Extract invoices from source.

        Args:
            source: Source configuration
            event: SourceExecuteEvent with parameters

        Returns:
            List of extracted invoices
        """
        try:
            # Use source runner to execute extraction
            invoices = await asyncio.to_thread(
                self.source_runner.run,
                source_type=source.type,
                from_date=event.from_date,
                max_results=event.max_results or source.max_results,
                extraction_params=source.extraction_params,
                email_sender_from=source.email_sender_from,
                email_subject_contains=source.email_subject_contains,
            )

            return invoices if invoices else []

        except Exception as e:
            logger.error(f"Failed to extract invoices from source: {e}", exc_info=True)
            return []


async def run_source_worker(
    nats_servers: List[str],
    db_url: str,
) -> None:
    """Run source worker.

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
        worker = SourceWorker(nats_client)
        await worker.start()

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Source worker shutting down")
    except Exception as e:
        logger.error(f"Source worker error: {e}", exc_info=True)
    finally:
        await close_nats_client()
