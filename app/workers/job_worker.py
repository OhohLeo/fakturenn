"""Unified job worker for executing complete automation workflows."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_manager
from app.db.models import (
    Automation,
    Export,
    ExportHistory,
    Job,
    Source,
    SourceExportMapping,
)
from app.export.base import get_export_handler
from app.nats import (
    JobCompletedEvent,
    JobFailedEvent,
    JobStartedEvent,
    NatsClient,
)
from app.sources.invoice import Invoice
from app.sources.runner import SourceRunner

logger = logging.getLogger(__name__)


class JobWorker:
    """Unified worker that executes complete job workflows."""

    def __init__(self, nats_client: NatsClient):
        """Initialize job worker.

        Args:
            nats_client: NATS client for messaging
        """
        self.nats = nats_client
        self.db_manager = get_db_manager()
        self.source_runner = SourceRunner()

    async def start(self) -> None:
        """Start the job worker."""
        # Set up NATS stream and consumer
        await self.nats.ensure_stream(
            "jobs",
            ["job.started", "job.completed", "job.failed"],
        )

        await self.nats.ensure_consumer(
            "jobs",
            "job_worker_consumer",
            "job.started",
        )

        # Subscribe to job started events
        async def handle_job_started(data: dict):
            event = JobStartedEvent(**data)
            await self.handle_job_started(event)

        await self.nats.subscribe_jetstream(
            "jobs",
            "job_worker_consumer",
            handle_job_started,
        )

        logger.info("Job worker started")

    async def handle_job_started(self, event: JobStartedEvent) -> None:
        """Handle job started event - execute complete automation workflow.

        Args:
            event: JobStartedEvent message
        """
        job_id = event.job_id
        automation_id = event.automation_id
        user_id = event.user_id
        started_at = datetime.now(UTC)

        logger.info(f"Job {job_id} started for automation {automation_id}")

        try:
            async with self.db_manager.get_session() as session:
                # Update job status to running
                await self._update_job_status(
                    session, job_id, "running", started_at=started_at
                )

                # Get automation and sources from database
                automation = await self._get_automation(session, automation_id, user_id)
                if not automation:
                    raise ValueError(f"Automation {automation_id} not found")

                sources = await self._get_active_sources(session, automation_id)
                exports = await self._get_active_exports(session, automation_id)

                if not sources:
                    raise ValueError("No sources configured for automation")

                if not exports:
                    raise ValueError("No exports configured for automation")

            # Execute workflow: extract from all sources, export all invoices
            stats = await self._execute_workflow(
                job_id,
                automation_id,
                user_id,
                sources,
                exports,
                event.from_date,
                event.max_results,
            )

            # Mark job as completed
            async with self.db_manager.get_session() as session:
                await self._complete_job(
                    session,
                    job_id,
                    automation_id,
                    user_id,
                    stats,
                )

        except Exception as e:
            logger.error(f"Failed to execute job {job_id}: {e}", exc_info=True)
            await self._fail_job(
                job_id,
                automation_id,
                user_id,
                f"Job execution failed: {str(e)}",
            )

    async def _execute_workflow(
        self,
        job_id: int,
        automation_id: int,
        user_id: int,
        sources: List[Source],
        exports: List[Export],
        from_date: Optional[str],
        max_results: Optional[int],
    ) -> dict:
        """Execute complete workflow: extract from sources, export invoices.

        Args:
            job_id: Job ID
            automation_id: Automation ID
            user_id: User ID
            sources: List of sources to extract from
            exports: List of exports to execute
            from_date: Start date for extraction
            max_results: Maximum results to fetch

        Returns:
            Job statistics dictionary
        """
        stats = {
            "sources_executed": 0,
            "invoices_extracted": 0,
            "exports_completed": 0,
            "exports_failed": 0,
            "duration_seconds": 0,
        }

        start_time = datetime.now(UTC)

        try:
            # Extract invoices from all sources
            all_invoices: List[tuple[Invoice, Source]] = []

            for source in sources:
                logger.info(
                    f"Extracting invoices from source {source.id} ({source.name})"
                )

                try:
                    invoices = await self._extract_invoices(
                        source,
                        from_date,
                        max_results,
                    )

                    logger.info(
                        f"Extracted {len(invoices)} invoices from source {source.id}"
                    )
                    stats["sources_executed"] += 1
                    stats["invoices_extracted"] += len(invoices)

                    # Store invoices with source reference
                    for invoice in invoices:
                        all_invoices.append((invoice, source))

                except Exception as e:
                    logger.error(
                        f"Failed to extract from source {source.id}: {e}", exc_info=True
                    )

            if not all_invoices:
                logger.warning("No invoices extracted from any source")
                stats["duration_seconds"] = int(
                    (datetime.now(UTC) - start_time).total_seconds()
                )
                return stats

            # Execute exports for each invoice
            async with self.db_manager.get_session() as session:
                export_mappings = await self._get_all_export_mappings(session)

            for invoice, source in all_invoices:
                # Find exports mapped to this source
                mapped_exports = [
                    m for m in export_mappings if m.source_id == source.id
                ]

                if not mapped_exports:
                    logger.warning(f"No exports mapped for source {source.id}")
                    continue

                for mapping in mapped_exports:
                    export_id = mapping.export_id

                    # Find export configuration
                    export = next((e for e in exports if e.id == export_id), None)
                    if not export:
                        logger.warning(f"Export {export_id} not found")
                        continue

                    try:
                        # Build context for export
                        context = {
                            "invoice_id": invoice.invoice_id,
                            "date": invoice.date if invoice.date else "",
                            "amount_eur": float(invoice.amount)
                            if invoice.amount
                            else 0.0,
                            "month": invoice.date.split("-")[1] if invoice.date else "",
                            "year": invoice.date.split("-")[0] if invoice.date else "",
                            "source": source.name,
                        }

                        invoice_data = {
                            "file_path": str(invoice.file_path),
                            "amount_eur": float(invoice.amount)
                            if invoice.amount
                            else None,
                        }

                        # Execute export
                        result = await self._execute_export(
                            export,
                            invoice_data,
                            context,
                        )

                        # Record export history
                        async with self.db_manager.get_session() as session:
                            await self._create_export_history(
                                session,
                                job_id,
                                export_id,
                                export.type,
                                result["status"],
                                context,
                                result.get("external_reference"),
                                result.get("error_message"),
                            )

                        if result["status"] in ("success", "duplicate_skipped"):
                            stats["exports_completed"] += 1
                            logger.info(
                                f"Export {export_id} completed for invoice {invoice.invoice_id}"
                            )
                        else:
                            stats["exports_failed"] += 1
                            logger.error(
                                f"Export {export_id} failed: {result.get('error_message')}"
                            )

                    except Exception as e:
                        stats["exports_failed"] += 1
                        logger.error(
                            f"Failed to execute export {export_id}: {e}",
                            exc_info=True,
                        )

                        # Record failed export
                        async with self.db_manager.get_session() as session:
                            await self._create_export_history(
                                session,
                                job_id,
                                export_id,
                                export.type,
                                "failed",
                                context if "context" in locals() else {},
                                None,
                                str(e),
                            )

        finally:
            stats["duration_seconds"] = int(
                (datetime.now(UTC) - start_time).total_seconds()
            )

        return stats

    async def _extract_invoices(
        self,
        source: Source,
        from_date: Optional[str],
        max_results: Optional[int],
    ) -> List[Invoice]:
        """Extract invoices from a source.

        Args:
            source: Source configuration
            from_date: Start date for extraction
            max_results: Maximum results to fetch

        Returns:
            List of extracted invoices
        """
        try:
            invoices = await asyncio.to_thread(
                self.source_runner.run,
                source_type=source.type,
                from_date=from_date,
                max_results=max_results or source.max_results,
                extraction_params=source.extraction_params,
                email_sender_from=source.email_sender_from,
                email_subject_contains=source.email_subject_contains,
            )
            return invoices if invoices else []
        except Exception as e:
            logger.error(f"Failed to extract invoices from source: {e}", exc_info=True)
            raise

    async def _execute_export(
        self,
        export: Export,
        invoice_data: dict,
        context: dict,
    ) -> dict:
        """Execute export handler.

        Args:
            export: Export configuration
            invoice_data: Invoice data to export
            context: Export context variables

        Returns:
            Result dictionary with status and optional reference/error
        """
        try:
            handler = get_export_handler(export.type, export.configuration)
            result = await handler.export(invoice_data, context)

            return {
                "status": result.status,
                "external_reference": result.external_reference,
                "error_message": result.error_message,
            }
        except Exception as e:
            logger.error(f"Failed to execute export: {e}", exc_info=True)
            return {
                "status": "failed",
                "external_reference": None,
                "error_message": str(e),
            }

    async def _get_automation(
        self,
        session: AsyncSession,
        automation_id: int,
        user_id: int,
    ) -> Optional[Automation]:
        """Get automation by ID.

        Args:
            session: Database session
            automation_id: Automation ID
            user_id: User ID for verification

        Returns:
            Automation object or None
        """
        stmt = select(Automation).where(
            Automation.id == automation_id,
            Automation.user_id == user_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_active_sources(
        self,
        session: AsyncSession,
        automation_id: int,
    ) -> List[Source]:
        """Get active sources for automation.

        Args:
            session: Database session
            automation_id: Automation ID

        Returns:
            List of active sources
        """
        stmt = select(Source).where(
            Source.automation_id == automation_id,
            Source.active.is_(True),
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def _get_active_exports(
        self,
        session: AsyncSession,
        automation_id: int,
    ) -> List[Export]:
        """Get active exports for automation.

        Args:
            session: Database session
            automation_id: Automation ID

        Returns:
            List of active exports
        """
        stmt = select(Export).where(
            Export.automation_id == automation_id,
            Export.active.is_(True),
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def _get_all_export_mappings(
        self,
        session: AsyncSession,
    ) -> List[SourceExportMapping]:
        """Get all export mappings from session.

        Args:
            session: Database session

        Returns:
            List of all export mappings
        """
        stmt = select(SourceExportMapping)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def _update_job_status(
        self,
        session: AsyncSession,
        job_id: int,
        status: str,
        started_at: Optional[datetime] = None,
    ) -> None:
        """Update job status in database.

        Args:
            session: Database session
            job_id: Job ID
            status: New status
            started_at: Optional started timestamp
        """
        stmt = select(Job).where(Job.id == job_id)
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()

        if job:
            job.status = status
            if started_at:
                job.started_at = started_at
            if status in ("completed", "failed"):
                job.completed_at = datetime.now(UTC)
            await session.commit()

    async def _complete_job(
        self,
        session: AsyncSession,
        job_id: int,
        automation_id: int,
        user_id: int,
        stats: dict,
    ) -> None:
        """Complete job successfully.

        Args:
            session: Database session
            job_id: Job ID
            automation_id: Automation ID
            user_id: User ID
            stats: Job statistics
        """
        try:
            # Update job status
            stmt = select(Job).where(Job.id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if job:
                job.status = "completed"
                job.completed_at = datetime.now(UTC)
                job.stats = stats
                await session.commit()

            # Publish completion event
            event = JobCompletedEvent(
                job_id=job_id,
                automation_id=automation_id,
                user_id=user_id,
                stats=stats,
            )
            await self.nats.publish(
                "job.completed",
                event.model_dump(mode="json"),
            )

            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Failed to complete job {job_id}: {e}", exc_info=True)

    async def _fail_job(
        self,
        job_id: int,
        automation_id: int,
        user_id: int,
        error_message: str,
    ) -> None:
        """Fail job.

        Args:
            job_id: Job ID
            automation_id: Automation ID
            user_id: User ID
            error_message: Error description
        """
        try:
            async with self.db_manager.get_session() as session:
                stmt = select(Job).where(Job.id == job_id)
                result = await session.execute(stmt)
                job = result.scalar_one_or_none()

                if job:
                    job.status = "failed"
                    job.completed_at = datetime.now(UTC)
                    job.error_message = error_message
                    await session.commit()

            # Publish failure event
            event = JobFailedEvent(
                job_id=job_id,
                automation_id=automation_id,
                user_id=user_id,
                error_message=error_message,
            )
            await self.nats.publish(
                "job.failed",
                event.model_dump(mode="json"),
            )

            logger.error(f"Job {job_id} failed: {error_message}")

        except Exception as e:
            logger.error(f"Failed to fail job {job_id}: {e}", exc_info=True)

    async def _create_export_history(
        self,
        session: AsyncSession,
        job_id: int,
        export_id: int,
        export_type: str,
        status: str,
        context: dict,
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
                exported_at=datetime.now(UTC),
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


async def run_job_worker(
    nats_servers: List[str],
    db_url: str,
) -> None:
    """Run job worker.

    Args:
        nats_servers: List of NATS server URLs
        db_url: Database connection URL
    """
    # Initialize dependencies
    from app.nats import close_nats_client, init_nats_client
    from app.db.connection import init_db_manager

    # Initialize database
    init_db_manager(db_url)

    # Initialize NATS
    nats_client = await init_nats_client(nats_servers)

    try:
        # Create and start worker
        worker = JobWorker(nats_client)
        await worker.start()

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Job worker shutting down")
    except Exception as e:
        logger.error(f"Job worker error: {e}", exc_info=True)
    finally:
        await close_nats_client()
