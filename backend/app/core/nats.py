"""NATS JetStream client for async messaging.

Provides message publishing for job triggers and record processing.

Streams:
    JOBS - Job trigger messages (source sync requests)
    RECORDS - Record processing messages (parse, export)
    EXPORTS - Export trigger messages

Subjects:
    jobs.trigger - Trigger a job for a source
    records.parse - Parse raw data into records
    records.export - Export a record to destinations
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import nats
from nats.js import JetStreamContext
from pydantic import BaseModel

from app.core.config import settings


class NATSError(Exception):
    """Raised when NATS operations fail."""

    pass


# ============================================================================
# MESSAGE SCHEMAS
# ============================================================================


class JobMessage(BaseModel):
    """Message to trigger a job for a source.

    Published to: jobs.trigger
    """

    job_id: UUID
    source_id: UUID
    workflow_id: UUID
    triggered_at: datetime
    triggered_by: str = "scheduler"  # scheduler, manual, api


class RecordParseMessage(BaseModel):
    """Message to parse raw data into records.

    Published to: records.parse
    """

    job_id: UUID
    source_id: UUID
    workflow_id: UUID


class RecordExportMessage(BaseModel):
    """Message to export a record to destinations.

    Published to: records.export
    """

    record_id: UUID
    workflow_id: UUID
    exporter_ids: list[UUID] | None = None  # None = all active exporters


# ============================================================================
# NATS CLIENT
# ============================================================================


class NATSClient:
    """NATS JetStream client for publishing and subscribing to messages."""

    # Stream configurations
    STREAMS = {
        "JOBS": {
            "name": "JOBS",
            "subjects": ["jobs.>"],
            "retention": "limits",
            "max_msgs": 10000,
            "max_age": 86400 * 7,  # 7 days
        },
        "RECORDS": {
            "name": "RECORDS",
            "subjects": ["records.>"],
            "retention": "limits",
            "max_msgs": 100000,
            "max_age": 86400 * 7,  # 7 days
        },
    }

    def __init__(self, url: str | None = None):
        """Initialize NATS client.

        Args:
            url: NATS server URL (default from settings)
        """
        self.url = url or settings.NATS_URL
        self._nc: nats.NATS | None = None
        self._js: JetStreamContext | None = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to NATS."""
        return self._nc is not None and self._nc.is_connected

    async def connect(self) -> None:
        """Connect to NATS server and setup JetStream."""
        try:
            self._nc = await nats.connect(self.url)
            self._js = self._nc.jetstream()

            # Ensure streams exist
            await self._setup_streams()

        except Exception as e:
            raise NATSError(f"Failed to connect to NATS: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self._nc:
            await self._nc.close()
        self._nc = None
        self._js = None

    async def _setup_streams(self) -> None:
        """Create JetStream streams if they don't exist."""
        if not self._js:
            raise NATSError("Not connected to NATS")

        for stream_config in self.STREAMS.values():
            try:
                await self._js.add_stream(**stream_config)
            except nats.js.errors.BadRequestError:
                # Stream already exists, update it
                await self._js.update_stream(**stream_config)

    async def publish_job(self, message: JobMessage) -> None:
        """Publish a job trigger message.

        Args:
            message: Job message to publish
        """
        await self._publish("jobs.trigger", message)

    async def publish_record_parse(self, message: RecordParseMessage) -> None:
        """Publish a record parse message.

        Args:
            message: Record parse message
        """
        await self._publish("records.parse", message)

    async def publish_record_export(self, message: RecordExportMessage) -> None:
        """Publish a record export message.

        Args:
            message: Record export message
        """
        await self._publish("records.export", message)

    async def _publish(self, subject: str, message: BaseModel) -> None:
        """Publish a message to a subject.

        Args:
            subject: NATS subject
            message: Pydantic message to publish
        """
        if not self._js:
            raise NATSError("Not connected to NATS")

        try:
            data = message.model_dump_json().encode()
            await self._js.publish(subject, data)
        except Exception as e:
            raise NATSError(f"Failed to publish message: {e}") from e

    async def __aenter__(self) -> "NATSClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()


# Global client instance
_nats_client: NATSClient | None = None


async def get_nats() -> NATSClient:
    """Get or create NATS client singleton."""
    global _nats_client
    if _nats_client is None or not _nats_client.is_connected:
        _nats_client = NATSClient()
        await _nats_client.connect()
    return _nats_client


async def publish_job_trigger(
    job_id: UUID,
    source_id: UUID,
    workflow_id: UUID,
    triggered_by: str = "api",
) -> None:
    """Convenience function to publish a job trigger.

    Args:
        job_id: UUID of the Job record
        source_id: UUID of the Source to sync
        workflow_id: UUID of the Workflow
        triggered_by: Who triggered the job (scheduler, manual, api)
    """
    client = await get_nats()
    message = JobMessage(
        job_id=job_id,
        source_id=source_id,
        workflow_id=workflow_id,
        triggered_at=datetime.utcnow(),
        triggered_by=triggered_by,
    )
    await client.publish_job(message)


async def publish_record_export(
    record_id: UUID,
    workflow_id: UUID,
    exporter_ids: list[UUID] | None = None,
) -> None:
    """Convenience function to publish a record export request.

    Args:
        record_id: UUID of the Record to export
        workflow_id: UUID of the Workflow
        exporter_ids: Optional list of specific exporters (None = all)
    """
    client = await get_nats()
    message = RecordExportMessage(
        record_id=record_id,
        workflow_id=workflow_id,
        exporter_ids=exporter_ids,
    )
    await client.publish_record_export(message)
