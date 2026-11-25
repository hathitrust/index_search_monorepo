import json
import threading
from typing import Any, cast

import pika.exceptions
from ht_utils.ht_errors import HTError
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import get_queue_message_id
from pika.adapters.blocking_connection import BlockingChannel

from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_manager import QueueManager
from ht_queue_service.queue_settings import QueueSettings
from ht_queue_service.queue_connection import QueueConnection

logger = get_ht_logger(name=__name__)

DELIVERY_MODE_PERSISTENT = 2  # Make message persistent


class MessageTooLargeError(HTError):
    """The serialized message is larger than QueueSettings.max_message_size; it is not published."""


class PublishError(HTError):
    """Base class for publish failures. Callers catch our types, never pika's."""


class PublishRefusedError(PublishError):
    """The broker nacked the message (for example, a disk alarm or an internal error)."""


class PublishUnroutableError(PublishError):
    """The broker returned the message because no queue is bound to receive it."""


class PublishConnectionError(PublishError):
    """The connection or channel was lost while publishing. The producer does not reconnect:
    the caller should count the item as failed and exit so the orchestrator restarts the process."""


class QueueProducer:
    """
    Publish messages to a RabbitMQ queue with automatic queue setup and per-thread channels.

    This producer:
    - Creates a channel via `ChannelCreator` and ensures the target queue/exchange are declared
      and ready via `QueueManager`.
    - Uses a thread-local channel for each non-main thread to avoid sharing non-thread-safe
      Pika channels across threads.
    - Makes published messages persistent (delivery mode = 2) and JSON-encodes payloads.
    - Turns on publisher confirms and publishes with `mandatory=True`, so a nacked or
      unroutable message raises instead of being lost silently.
    - Never reconnects: a lost connection raises `PublishConnectionError`.

    Attributes:
        channel_creator: Factory that manages the underlying connection and creates channels.
        channel: The primary channel used by the main thread.
        _thread_local: Thread-local storage where per-thread channels are cached.
        queue_manager: Manages queue/exchange declaration and readiness checks.

    Notes:
        - Channels are not thread-safe. Each non-main thread gets its own channel.
        - Publishing is not retried. It raises `PublishRefusedError` (nack),
          `PublishUnroutableError` (returned) or `PublishConnectionError` (connection lost).
          Oversized messages raise `MessageTooLargeError` before any publish attempt.
    """

    def __init__(self, queue_settings: QueueSettings, queue_connection: QueueConnection) -> None:
        """
        Initialize the producer and ensure the queue infrastructure is ready.

        :param queue_settings: queue configuration object containing queue_name, exchange_name,
        exchange_type, durable, routing_key, and queue_arguments.
        :param queue_connection: Pre-established QueueConnection. If not provided, a new connection is created.

        Behaviour:
        - Build a ChannelCreator and opens an initial channel for the main thread.
        - Initialize thread-local storage for per-thread channels.
        - Build a QueueManager to handle queue/exchange setup.
        - Turn on publisher confirms on the channel.
        - Check if the queue is ready; if not, set it up.

        """
        # Define credentials (user/password) as environment variables
        # declaring the credentials needed for connection like host, port, username, password, exchange etc

        self.queue_connection = queue_connection

        try:
            # Object to create channels
            self.channel = self._open_channel()

            # Thread-local storage for channels (for multi-threading support)
            self._thread_local = threading.local()

            # Object to create the queue and manage its setup and attributes
            self.queue_manager = QueueManager(queue_settings)

            # Ensure the queue is ready when the producer is initialized
            if not self.queue_manager.is_ready(self.channel):
                logger.warning("Queue setup not ready. Initializing channel and setup.")
                # is_ready() leaves the channel closed when the queue is missing: open a new one
                self.channel = self._open_channel()
                self.queue_manager.set_up_queue(self.channel)
        except pika.exceptions.AMQPError as err:
            raise PublishConnectionError(f"Unable to set up the queue: {err}") from err

    def _open_channel(self) -> BlockingChannel:
        """Open a channel with publisher confirms turned on.

        :raises PublishConnectionError: when the channel cannot be opened or confirms cannot be
            enabled. `QueueConnection` wraps pika errors in `RuntimeError`.
        """
        try:
            channel = self.queue_connection.channel()
        except RuntimeError as err:
            raise PublishConnectionError(f"Unable to establish a RabbitMQ channel: {err}") from err
        if channel is None:
            raise PublishConnectionError("Unable to establish a RabbitMQ channel")
        try:
            channel.confirm_delivery()
        except pika.exceptions.AMQPError as err:
            raise PublishConnectionError(f"Unable to enable publisher confirms: {err}") from err
        return channel

    def _discard_thread_channel(self) -> None:
        """Forget this thread's channel after a failure, so the next publish opens a fresh one
        instead of failing forever on a closed channel. This is not a reconnect: if the
        connection is gone, opening the channel raises PublishConnectionError."""
        if threading.current_thread() is not threading.main_thread():
            self._thread_local.channel = None

    def _get_thread_channel(self) -> BlockingChannel | None:
        """
        Get a thread-local channel. Creates one if it doesn't exist for this thread.
        For single-threaded usage (main thread), returns the original self.channel for compatibility.

        Notes:
            Channels must not be shared across threads. Each non-main thread gets its own channel.
        """
        # Check if we're in the main thread (backward compatibility)
        if threading.current_thread() is threading.main_thread():
            return self.channel

        # For other threads, use thread-local channels
        if not getattr(self._thread_local, "channel", None):
            self._thread_local.channel = self._open_channel()
            # Set up queue for this thread's channel
            self.queue_manager.set_up_queue(self._thread_local.channel)

        return cast(BlockingChannel | None, self._thread_local.channel)

    def publish_messages(self, queue_message: dict[str, Any]) -> None:
        # TODO: Define a dataclass for the queue message to ensure type safety and validation

        """
        Serialize and publish the message using thread-safe channel management.

        Behaviour:
         - Serializes the message to JSON before any channel work. A serialization error is
           raised without a retry.
         - If the serialized message is larger than `queue_manager.max_message_size`, raises
           `MessageTooLargeError` before contacting the broker.
         - Publishes with `mandatory=True` on a channel with publisher confirms, and returns
           only after the broker confirms. There is no retry and no reconnect.
        :param queue_message: The message to be published should be a dictionary.
        :return: None

        :raises TypeError, ValueError: when the message cannot be serialized to JSON.
        :raises MessageTooLargeError: when the serialized body exceeds `max_message_size`.
        :raises PublishRefusedError: when the broker nacks the message.
        :raises PublishUnroutableError: when the broker returns the message (no binding).
        :raises PublishConnectionError: when the connection or channel is lost.
        """

        ht_id = get_queue_message_id(queue_message)

        try:
            body = json.dumps(queue_message).encode("utf-8")
        except (TypeError, ValueError) as json_err:
            logger.error(
                "Failed to serialize message",
                ht_id=ht_id,
                error=str(json_err),
                exc_info=True,
            )
            raise

        size = len(body)
        limit = self.queue_manager.max_message_size
        if size > limit:
            # Logged as fields so a search on ht_id finds this failure too (ETT-2018)
            logger.error(
                "Message too large, not published",
                ht_id=ht_id,
                size=size,
                limit=limit,
            )
            raise MessageTooLargeError(
                f"Message ht_id={ht_id} size {size} bytes exceeds max_message_size {limit} bytes; not published"
            )

        try:
            channel = self._get_thread_channel()
            if channel is None or channel.is_closed:
                raise PublishConnectionError(
                    f"Channel closed before publish (queue: {self.queue_manager.queue_name}), ht_id={ht_id}"
                )

            channel.basic_publish(
                exchange=self.queue_manager.main_exchange_name,
                routing_key=self.queue_manager.queue_name,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=DELIVERY_MODE_PERSISTENT, content_type="application/json"
                ),  # make a message persistent
                mandatory=True,
            )
        except PublishConnectionError as err:
            self._discard_thread_channel()
            logger.error("Connection lost, message not published", ht_id=ht_id, error=str(err))
            raise
        except pika.exceptions.UnroutableError as err:
            logger.error(
                "Message returned by the broker, not published",
                ht_id=ht_id,
                queue=self.queue_manager.queue_name,
            )
            raise PublishUnroutableError(
                f"Message ht_id={ht_id} was returned: no queue bound"
            ) from err
        except pika.exceptions.NackError as err:
            logger.error(
                "Message nacked by the broker, not published",
                ht_id=ht_id,
                queue=self.queue_manager.queue_name,
            )
            raise PublishRefusedError(f"Message ht_id={ht_id} was nacked by the broker") from err
        except pika.exceptions.AMQPError as err:
            self._discard_thread_channel()
            # ChannelClosed, ConnectionClosed, StreamLostError, ChannelWrongStateError, ...
            logger.error(
                "Connection lost, message not published",
                ht_id=ht_id,
                queue=self.queue_manager.queue_name,
                error=str(err),
            )
            raise PublishConnectionError(
                f"Connection lost publishing ht_id={ht_id}: {err}"
            ) from err

        logger.info(
            "published_message",
            ht_id=ht_id,
            queue=self.queue_manager.queue_name,
            size=size,
        )
