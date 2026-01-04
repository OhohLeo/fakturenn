"""FastStream worker application for async job processing.

Handles:
- jobs.trigger - Process source sync jobs
- records.export - Export records to destinations
"""

import logging

from faststream import FastStream
from faststream.nats import JStream, NatsBroker

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create NATS broker
broker = NatsBroker(settings.NATS_URL)

# Create FastStream application
app = FastStream(broker)

# Define streams
jobs_stream = JStream(
    name="JOBS",
    subjects=["jobs.>"],
)

records_stream = JStream(
    name="RECORDS",
    subjects=["records.>"],
)


@app.on_startup
async def on_startup() -> None:
    """Initialize resources on startup."""
    logger.info("Worker starting up")
    logger.info(f"Connected to NATS at {settings.NATS_URL}")


@app.on_shutdown
async def on_shutdown() -> None:
    """Cleanup resources on shutdown."""
    logger.info("Worker shutting down")


# Import handlers to register them with the broker
from app.worker.handlers import export_handler, job_handler  # noqa: E402, F401
