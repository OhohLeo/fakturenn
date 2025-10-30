"""NATS event-driven messaging module."""

from app.nats.client import (
    NatsClient,
    get_nats_client,
    init_nats_client,
    close_nats_client,
)
from app.nats.messages import (
    JobStartedEvent,
    JobCompletedEvent,
    JobFailedEvent,
)

__all__ = [
    "NatsClient",
    "get_nats_client",
    "init_nats_client",
    "close_nats_client",
    "JobStartedEvent",
    "JobCompletedEvent",
    "JobFailedEvent",
]
