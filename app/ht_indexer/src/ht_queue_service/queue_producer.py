import json
import threading
import time
from concurrent.futures import Future
from typing import Any, Literal, cast

import pika.exceptions
from ht_utils.ht_errors import HTError
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import get_queue_message_id
from pika.adapters.thread_safe_connection import Channel

from ht_queue_service.queue_connection import QueueConnection
from ht_queue_service.queue_manager import QueueManager
from ht_queue_service.queue_settings import QueueSettings

logger = get_ht_logger(name=__name__)

DELIVERY_MODE_PERSISTENT = 2  # Make message persistent
PUBLISH_CONFIRM_TIMEOUT = 30.0  # seconds; no confirm in this time means the outcome is unknown

PublishOutcome = Literal["ack", "nack", "returned"]


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


class _PublishChannel:
    """A channel plus its publisher-confirm state.

    pika calls on_return and on_confirm on the channel's worker thread; publish_messages waits on a
    Future in the caller's thread. One publish is in flight per channel, so no delivery tags are needed.
    pika calls on_return before on_confirm for the same message (same worker thread).
    """

    def __init__(self, channel: Channel) -> None:
        self.pika_channel = channel  # the pika channel; QueueManager and the tests use it directly
        self._lock = threading.Lock()  # callbacks and the caller touch the state below
        self._pending: Future[PublishOutcome] | None = None
        self._returned = False

    def enable_confirms(self) -> None:
        # Return callback first: the blocking confirm_delivery() below runs on the same I/O loop, so a dead
        # channel makes it raise. A failure of add_on_return_callback itself is only logged by pika.
        # As we use mandatory=True, we should add_on_return_callback() to know that the message has been rejected and
        # returned by the server.
        self.pika_channel.add_on_return_callback(self._on_return)
        # Use this callback to be notified by the broker when a message has been confirmed (ack) or rejected (nack).
        # The callback is called on the same I/O loop as the publish, so it is safe to call confirm_delivery()
        # after registering the callback.
        self.pika_channel.confirm_delivery(self._on_confirm)

    def begin(self) -> Future[Literal["ack", "nack", "returned"]] | None:
        """Call before basic_publish: a new Future per publish, so an old one can never be reused.
        The future is an object that holds the result or an exception.
        """
        with self._lock:
            self._returned = False
            self._pending = Future()
            return self._pending

    def _on_return(
        self, channel: Any, method: Any, properties: Any, body: bytes
    ) -> None:  # Any: untyped pika
        # The Basic.Ack that follows an unroutable publish is not proof the message reached a queue
        with self._lock:
            self._returned = True

    def _on_confirm(self, method_frame: Any) -> None:  # Any: pika frame type is untyped
        with self._lock:
            pending = self._pending
            if pending is None or pending.done():
                return  # a confirmation nobody is waiting for
            # The Basic.Ack or Basic.Nack that follows a publish is proof the message reached the broker.
            if isinstance(method_frame.method, pika.spec.Basic.Nack):
                pending.set_result("nack")
            elif self._returned:
                pending.set_result("returned")
            else:
                pending.set_result("ack")

    def await_outcome(self, future: Future[PublishOutcome]) -> PublishOutcome:
        deadline = time.monotonic() + PUBLISH_CONFIRM_TIMEOUT
        while True:
            try:
                return future.result(timeout=0.5)
            except TimeoutError:
                # A dead connection fires no callback, so poll the channel instead of waiting out the timeout
                if self.pika_channel.is_closed or time.monotonic() > deadline:
                    raise PublishConnectionError(
                        "No broker confirm: channel closed or timed out"
                    ) from None


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
            if not self.queue_manager.is_ready(self.channel.pika_channel):
                logger.warning("Queue setup not ready. Initializing channel and setup.")
                # is_ready() leaves the channel closed when the queue is missing: open a new one
                self.channel = self._open_channel()
                self.queue_manager.set_up_queue(self.channel.pika_channel)
        except pika.exceptions.AMQPError as err:
            raise PublishConnectionError(f"Unable to set up the queue: {err}") from err

    def _open_channel(self) -> _PublishChannel:
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
        publish_channel = _PublishChannel(channel)  # the pika channel is kept in .pika_channel
        try:
            publish_channel.enable_confirms()
        except pika.exceptions.AMQPError as err:
            raise PublishConnectionError(f"Unable to enable publisher confirms: {err}") from err
        return publish_channel

    def _discard_thread_channel(self) -> None:
        """Forget this thread's channel after a failure, so the next publish opens a fresh one
        instead of failing forever on a closed channel. This is not a reconnect: if the
        connection is gone, opening the channel raises PublishConnectionError."""
        if threading.current_thread() is not threading.main_thread():
            self._thread_local.channel = None

    def _get_thread_channel(self) -> _PublishChannel | None:
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
            self.queue_manager.set_up_queue(self._thread_local.channel.pika_channel)

        return cast(_PublishChannel | None, self._thread_local.channel)

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
            publish_channel = self._get_thread_channel()
            if publish_channel is None or publish_channel.pika_channel.is_closed:
                raise PublishConnectionError(
                    f"Channel closed before publish (queue: {self.queue_manager.queue_name}), ht_id={ht_id}"
                )
            # Initialize a new Future for this publish, so an old one can never be reused.
            # The future is an object that holds the result or an exception.
            outcome_future = publish_channel.begin()

            # Publish the message with mandatory=True to ensure it is routed to a queue.
            # It schedules the write on pika's IOLoop thread and returns immediately. Nothing is confirmed yet.
            publish_channel.pika_channel.basic_publish(
                exchange=self.queue_manager.main_exchange_name,
                routing_key=self.queue_manager.queue_name,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=DELIVERY_MODE_PERSISTENT, content_type="application/json"
                ),  # make a message persistent
                mandatory=True,
            )
            # Wait for the broker 0.5s to confirm the publish (ack/nack/returned) or raise on a lost connection.
            outcome = publish_channel.await_outcome(outcome_future)
        except PublishConnectionError as err:
            self._discard_thread_channel()
            logger.error("Connection lost, message not published", ht_id=ht_id, error=str(err))
            raise
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

        if outcome == "returned":
            logger.error(
                "Message returned by the broker, not published",
                ht_id=ht_id,
                queue=self.queue_manager.queue_name,
            )
            raise PublishUnroutableError(f"Message ht_id={ht_id} was returned: no queue bound")

        if outcome == "nack":
            logger.error(
                "Message nacked by the broker, not published",
                ht_id=ht_id,
                queue=self.queue_manager.queue_name,
            )
            raise PublishRefusedError(f"Message ht_id={ht_id} was nacked by the broker")

        logger.info(
            "published_message",
            ht_id=ht_id,
            queue=self.queue_manager.queue_name,
            size=size,
        )
