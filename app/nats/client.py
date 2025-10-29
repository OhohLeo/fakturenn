"""NATS client for event-driven messaging."""

import json
import logging
from typing import Callable, Optional

import nats
from nats.aio.client import Client as NatsClient
from nats.errors import NoServersError
from nats.js.api import RetentionPolicy

logger = logging.getLogger(__name__)

# Singleton instance
_nats_client: Optional["NatsClientWrapper"] = None


class NatsClientWrapper:
    """Wrapper around NATS client with connection management and JetStream support."""

    def __init__(self, servers: list[str]):
        """Initialize NATS client.

        Args:
            servers: List of NATS server URLs (e.g., ["nats://localhost:4222"])
        """
        self.servers = servers
        self.client: Optional[NatsClient] = None
        self.js = None

    async def connect(self) -> None:
        """Connect to NATS servers."""
        try:
            self.client = await nats.connect(servers=self.servers, name="fakturenn-app")
            self.js = self.client.jetstream()
            logger.info(f"Connected to NATS servers: {self.servers}")
        except NoServersError as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from NATS."""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from NATS")

    async def ensure_stream(
        self,
        stream_name: str,
        subjects: list[str],
        max_age: int = 24 * 60 * 60,  # 24 hours in seconds
    ) -> None:
        """Ensure JetStream stream exists with given configuration.

        Args:
            stream_name: Name of the stream
            subjects: List of subjects to listen to
            max_age: Maximum age of messages in seconds (default 24 hours)
        """
        if not self.js:
            raise RuntimeError("Not connected to NATS")

        try:
            await self.js.stream_info(stream_name)
            logger.debug(f"Stream '{stream_name}' already exists")
        except Exception:
            logger.info(f"Creating stream '{stream_name}'")
            try:
                await self.js.add_stream(
                    name=stream_name,
                    subjects=subjects,
                    max_age=max_age * 10**9,  # Convert to nanoseconds
                    retention=RetentionPolicy.LIMITS,
                )
                logger.info(f"Stream '{stream_name}' created successfully")
            except Exception as e:
                logger.error(f"Failed to create stream '{stream_name}': {e}")
                raise

    async def ensure_consumer(
        self,
        stream_name: str,
        consumer_name: str,
        filter_subject: str,
    ) -> None:
        """Ensure JetStream consumer exists.

        Args:
            stream_name: Name of the stream
            consumer_name: Name of the consumer
            filter_subject: Subject to filter by
        """
        if not self.js:
            raise RuntimeError("Not connected to NATS")

        try:
            await self.js.consumer_info(stream_name, consumer_name)
            logger.debug(f"Consumer '{consumer_name}' already exists")
        except Exception:
            logger.info(f"Creating consumer '{consumer_name}'")
            try:
                await self.js.add_consumer(
                    stream_name,
                    durable_name=consumer_name,
                    filter_subject=filter_subject,
                )
                logger.info(f"Consumer '{consumer_name}' created successfully")
            except Exception as e:
                logger.error(f"Failed to create consumer '{consumer_name}': {e}")
                raise

    async def publish(self, subject: str, data: dict) -> None:
        """Publish a message to a subject.

        Args:
            subject: Subject to publish to
            data: Dictionary to serialize as JSON
        """
        if not self.client:
            raise RuntimeError("Not connected to NATS")

        try:
            payload = json.dumps(data).encode()
            if self.js:
                await self.js.publish(subject, payload)
            else:
                await self.client.publish(subject, payload)
            logger.debug(f"Published to {subject}")
        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")
            raise

    async def subscribe(
        self,
        subject: str,
        callback: Callable,
        queue_group: Optional[str] = None,
    ) -> None:
        """Subscribe to a subject with a callback.

        Args:
            subject: Subject to subscribe to
            callback: Async callback function to handle messages
            queue_group: Optional queue group for load balancing
        """
        if not self.client:
            raise RuntimeError("Not connected to NATS")

        async def msg_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await callback(data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode message: {e}")
            except Exception as e:
                logger.error(f"Error in message callback: {e}")

        try:
            await self.client.subscribe(subject, cb=msg_handler, queue=queue_group)
            logger.info(f"Subscribed to {subject}")
        except Exception as e:
            logger.error(f"Failed to subscribe to {subject}: {e}")
            raise

    async def subscribe_jetstream(
        self,
        stream_name: str,
        consumer_name: str,
        callback: Callable,
        deliver_subject: Optional[str] = None,
    ) -> None:
        """Subscribe to JetStream consumer.

        Args:
            stream_name: Name of the stream
            consumer_name: Name of the consumer
            callback: Async callback function to handle messages
            deliver_subject: Optional custom deliver subject
        """
        if not self.js:
            raise RuntimeError("Not connected to JetStream")

        async def msg_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await callback(data)
                # Acknowledge message after successful processing
                await msg.ack()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode message: {e}")
                # Negative acknowledge on decode error
                await msg.nak()
            except Exception as e:
                logger.error(f"Error in JetStream callback: {e}")
                # Negative acknowledge on processing error
                await msg.nak()

        try:
            await self.js.subscribe(
                consumer=consumer_name,
                stream=stream_name,
                cb=msg_handler,
            )
            logger.info(
                f"Subscribed to JetStream {stream_name}/{consumer_name}",
            )
        except Exception as e:
            logger.error(f"Failed to subscribe to JetStream: {e}")
            raise


def get_nats_client() -> NatsClientWrapper:
    """Get or create singleton NATS client.

    Returns:
        NatsClientWrapper instance

    Raises:
        RuntimeError: If client is not initialized
    """
    global _nats_client
    if _nats_client is None:
        raise RuntimeError("NATS client not initialized. Call init_nats_client first.")
    return _nats_client


async def init_nats_client(servers: list[str]) -> NatsClientWrapper:
    """Initialize singleton NATS client.

    Args:
        servers: List of NATS server URLs

    Returns:
        Initialized NatsClientWrapper instance
    """
    global _nats_client
    _nats_client = NatsClientWrapper(servers)
    await _nats_client.connect()
    return _nats_client


async def close_nats_client() -> None:
    """Close singleton NATS client."""
    global _nats_client
    if _nats_client:
        await _nats_client.disconnect()
        _nats_client = None
