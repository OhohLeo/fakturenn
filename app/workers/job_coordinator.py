"""Job coordinator worker for orchestrating automation workflows."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db_manager
from app.db.models import Automation, Job, Source
from app.nats import (
    NatsClient,
    JobStartedEvent,
    JobCompletedEvent,
    JobFailedEvent,
    SourceExecuteEvent,
)

logger = logging.getLogger(__name__)


class JobCoordinator:
    """Coordinates job execution workflow."""

    def __init__(self, nats_client: NatsClient):
        """Initialize job coordinator.

        Args:
            nats_client: NATS client for messaging
        """
        self.nats = nats_client
        self.db_manager = get_db_manager()
        # Track job state: {job_id: {source_id: status}}
        self.job_sources: Dict[int, Dict[int, str]] = {}
        # Track collected invoices: {job_id: [invoice_data]}
        self.job_invoices: Dict[int, List[Dict]] = {}

    async def start(self) -> None:
        """Start the job coordinator worker."""
        # Set up NATS streams and consumers
        await self.nats.ensure_stream(
            "job_events",
            ["job.started", "job.completed", "job.failed"],
        )

        await self.nats.ensure_consumer(
            "job_events",
            "coordinator_consumer",
            "job.started",
        )

        # Subscribe to job started events
        async def handle_job_started(data: dict):
            event = JobStartedEvent(**data)
            await self.handle_job_started(event)

        await self.nats.subscribe_jetstream(
            "job_events",
            "coordinator_consumer",
            handle_job_started,
        )

        logger.info("Job coordinator worker started")

    async def handle_job_started(self, event: JobStartedEvent) -> None:
        """Handle job started event.

        Args:
            event: JobStartedEvent message
        """
        job_id = event.job_id
        automation_id = event.automation_id
        user_id = event.user_id

        logger.info(
            f"Job {job_id} started for automation {automation_id}",
        )

        try:
            # Initialize job tracking
            self.job_sources[job_id] = {}
            self.job_invoices[job_id] = []

            # Get automation and sources from database
            async with self.db_manager.get_session() as session:
                automation = await self._get_automation(
                    session,
                    automation_id,
                    user_id,
                )
                if not automation:
                    raise ValueError(f"Automation {automation_id} not found")

                sources = await self._get_active_sources(session, automation_id)

                if not sources:
                    # No sources to execute, complete job immediately
                    await self._complete_job(
                        session,
                        job_id,
                        automation_id,
                        user_id,
                        stats={"sources_executed": 0, "exports_completed": 0},
                    )
                    return

                # Update job status to running
                await self._update_job_status(session, job_id, "running")

            # Publish source execute events
            for source in sources:
                self.job_sources[job_id][source.id] = "pending"

                source_event = SourceExecuteEvent(
                    job_id=job_id,
                    automation_id=automation_id,
                    user_id=user_id,
                    source_id=source.id,
                    source_type=source.type,
                    source_name=source.name,
                    from_date=event.from_date,
                    max_results=event.max_results,
                    extraction_params=source.extraction_params,
                )

                await self.nats.publish(
                    "source.execute",
                    source_event.model_dump(mode="json"),
                )
                logger.info(f"Published source execute event for source {source.id}")

            # Set timeout for job completion (30 minutes)
            asyncio.create_task(
                self._job_timeout(job_id, automation_id, user_id, timeout=1800),
            )

        except Exception as e:
            logger.error(f"Failed to handle job started event: {e}", exc_info=True)
            await self._fail_job(
                job_id,
                automation_id,
                user_id,
                f"Failed to start job: {str(e)}",
            )

    async def _get_automation(
        self,
        session: AsyncSession,
        automation_id: int,
        user_id: int,
    ) -> Optional[Automation]:
        """Get automation by ID and user.

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

    async def _update_job_status(
        self,
        session: AsyncSession,
        job_id: int,
        status: str,
    ) -> None:
        """Update job status in database.

        Args:
            session: Database session
            job_id: Job ID
            status: New status
        """
        stmt = select(Job).where(Job.id == job_id)
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()

        if job:
            job.status = status
            if status == "running":
                job.started_at = datetime.utcnow()
            elif status in ("completed", "failed"):
                job.completed_at = datetime.utcnow()
            await session.commit()

    async def _complete_job(
        self,
        session: AsyncSession,
        job_id: int,
        automation_id: int,
        user_id: int,
        stats: Optional[Dict] = None,
    ) -> None:
        """Complete job successfully.

        Args:
            session: Database session
            job_id: Job ID
            automation_id: Automation ID
            user_id: User ID
            stats: Optional job statistics
        """
        try:
            # Update job status
            stmt = select(Job).where(Job.id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if job:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
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

            # Clean up tracking
            if job_id in self.job_sources:
                del self.job_sources[job_id]
            if job_id in self.job_invoices:
                del self.job_invoices[job_id]

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
            # Update job status
            async with self.db_manager.get_session() as session:
                stmt = select(Job).where(Job.id == job_id)
                result = await session.execute(stmt)
                job = result.scalar_one_or_none()

                if job:
                    job.status = "failed"
                    job.completed_at = datetime.utcnow()
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

            # Clean up tracking
            if job_id in self.job_sources:
                del self.job_sources[job_id]
            if job_id in self.job_invoices:
                del self.job_invoices[job_id]

            logger.error(f"Job {job_id} failed: {error_message}")

        except Exception as e:
            logger.error(
                f"Failed to fail job {job_id}: {e}",
                exc_info=True,
            )

    async def _job_timeout(
        self,
        job_id: int,
        automation_id: int,
        user_id: int,
        timeout: int = 1800,
    ) -> None:
        """Wait for job completion or timeout.

        Args:
            job_id: Job ID
            automation_id: Automation ID
            user_id: User ID
            timeout: Timeout in seconds (default 30 minutes)
        """
        try:
            await asyncio.sleep(timeout)

            # Check if job is still running
            if job_id in self.job_sources:
                await self._fail_job(
                    job_id,
                    automation_id,
                    user_id,
                    f"Job timeout after {timeout} seconds",
                )
        except Exception as e:
            logger.error(f"Error in job timeout handler: {e}", exc_info=True)


async def run_job_coordinator(
    nats_servers: List[str],
    db_url: str,
) -> None:
    """Run job coordinator worker.

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
        # Create and start coordinator
        coordinator = JobCoordinator(nats_client)
        await coordinator.start()

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Job coordinator shutting down")
    except Exception as e:
        logger.error(f"Job coordinator error: {e}", exc_info=True)
    finally:
        await close_nats_client()
