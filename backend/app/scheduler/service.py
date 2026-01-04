"""APScheduler service for source sync scheduling.

Manages cron-based job triggers for sources.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.core.db import engine
from app.core.nats import JobMessage, get_nats
from app.models import Job, JobStatus, Source

logger = logging.getLogger(__name__)


class SchedulerError(Exception):
    """Raised when scheduler operations fail."""

    pass


class SchedulerService:
    """APScheduler-based service for managing source sync schedules.

    This service:
    - Loads active sources with crontab schedules from the database
    - Creates APScheduler jobs for each source
    - Publishes NATS messages when jobs are triggered
    - Supports dynamic schedule updates
    """

    def __init__(self) -> None:
        """Initialize scheduler service."""
        self.scheduler = AsyncIOScheduler()
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running and self.scheduler.running

    async def start(self) -> None:
        """Start the scheduler and load all source schedules."""
        if self._running:
            return

        logger.info("Starting scheduler service")

        # Load all active sources with schedules
        await self._load_schedules()

        # Start the scheduler
        self.scheduler.start()
        self._running = True

        logger.info("Scheduler service started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._running:
            return

        logger.info("Stopping scheduler service")
        self.scheduler.shutdown(wait=False)
        self._running = False
        logger.info("Scheduler service stopped")

    async def _load_schedules(self) -> None:
        """Load all active source schedules from the database."""
        with Session(engine) as session:
            statement = select(Source).where(
                Source.is_active == True,  # noqa: E712
                Source.crontab.isnot(None),
            )
            sources = session.exec(statement).all()

            for source in sources:
                if source.crontab:
                    await self.add_source_schedule(source)

            logger.info(f"Loaded {len(sources)} source schedules")

    async def add_source_schedule(self, source: Source) -> None:
        """Add or update a schedule for a source.

        Args:
            source: Source with crontab schedule
        """
        if not source.crontab:
            logger.warning(f"Source {source.id} has no crontab, skipping")
            return

        job_id = f"source_{source.id}"

        # Remove existing job if any
        existing = self.scheduler.get_job(job_id)
        if existing:
            self.scheduler.remove_job(job_id)

        try:
            # Parse crontab and create trigger
            trigger = CronTrigger.from_crontab(source.crontab)

            # Add job
            self.scheduler.add_job(
                self._trigger_source_job,
                trigger,
                args=[source.id, source.workflow_id],
                id=job_id,
                name=f"Source: {source.name}",
                replace_existing=True,
            )

            logger.info(
                f"Added schedule for source {source.id}: {source.crontab}"
            )

        except ValueError as e:
            logger.error(f"Invalid crontab for source {source.id}: {e}")
            raise SchedulerError(f"Invalid crontab: {e}") from e

    async def remove_source_schedule(self, source_id: UUID) -> None:
        """Remove schedule for a source.

        Args:
            source_id: Source UUID
        """
        job_id = f"source_{source_id}"
        existing = self.scheduler.get_job(job_id)

        if existing:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed schedule for source {source_id}")

    async def _trigger_source_job(
        self, source_id: UUID, workflow_id: UUID
    ) -> None:
        """Trigger a job for a source.

        Creates a Job record and publishes a NATS message.

        Args:
            source_id: Source UUID
            workflow_id: Workflow UUID
        """
        logger.info(f"Triggering job for source {source_id}")

        try:
            # Create Job record in database
            job_id = uuid4()
            now = datetime.utcnow()

            with Session(engine) as session:
                job = Job(
                    id=job_id,
                    source_id=source_id,
                    scheduled_at=now,
                    status=JobStatus.queued,
                )
                session.add(job)
                session.commit()

            # Publish NATS message
            nats = await get_nats()
            message = JobMessage(
                job_id=job_id,
                source_id=source_id,
                workflow_id=workflow_id,
                triggered_at=now,
                triggered_by="scheduler",
            )
            await nats.publish_job(message)

            logger.info(f"Published job {job_id} for source {source_id}")

        except Exception as e:
            logger.error(f"Failed to trigger job for source {source_id}: {e}")
            raise

    async def trigger_manual_job(
        self, source_id: UUID, workflow_id: UUID, triggered_by: str = "api"
    ) -> UUID:
        """Manually trigger a job for a source.

        Args:
            source_id: Source UUID
            workflow_id: Workflow UUID
            triggered_by: Who triggered the job (api, manual)

        Returns:
            Job UUID
        """
        logger.info(f"Manual job trigger for source {source_id} by {triggered_by}")

        # Create Job record
        job_id = uuid4()
        now = datetime.utcnow()

        with Session(engine) as session:
            job = Job(
                id=job_id,
                source_id=source_id,
                scheduled_at=now,
                status=JobStatus.queued,
            )
            session.add(job)
            session.commit()

        # Publish NATS message
        nats = await get_nats()
        message = JobMessage(
            job_id=job_id,
            source_id=source_id,
            workflow_id=workflow_id,
            triggered_at=now,
            triggered_by=triggered_by,
        )
        await nats.publish_job(message)

        logger.info(f"Published manual job {job_id} for source {source_id}")
        return job_id

    def get_next_run_time(self, source_id: UUID) -> datetime | None:
        """Get next scheduled run time for a source.

        Args:
            source_id: Source UUID

        Returns:
            Next run datetime or None if not scheduled
        """
        job_id = f"source_{source_id}"
        job = self.scheduler.get_job(job_id)

        if job and job.next_run_time:
            return job.next_run_time

        return None

    def get_scheduled_sources(self) -> list[dict[str, Any]]:
        """Get list of all scheduled sources.

        Returns:
            List of dicts with source_id, name, next_run_time
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            if job.id.startswith("source_"):
                source_id = job.id.replace("source_", "")
                jobs.append({
                    "source_id": source_id,
                    "name": job.name,
                    "next_run_time": job.next_run_time,
                })
        return jobs


# Global scheduler instance
_scheduler: SchedulerService | None = None


def get_scheduler() -> SchedulerService:
    """Get or create scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerService()
    return _scheduler
