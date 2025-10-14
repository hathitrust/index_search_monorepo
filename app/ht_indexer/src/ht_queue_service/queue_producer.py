# producer
import json
import threading
from typing import Any, Dict

import pika.exceptions
from ht_queue_service.queue_config import QueueParams

from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import FlexibleDict, get_queue_message_id

from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_manager import QueueManager

logger = get_ht_logger(name=__name__)

DELIVERY_MODE_PERSISTENT = 2  # Make message persistent

class QueueProducer:
    """
    Publish messages to a RabbitMQ queue with automatic queue setup and per-thread channels.

    This producer:
    - Creates a channel via `ChannelCreator` and ensures the target queue/exchange are declared
      and ready via `QueueManager`.
    - Uses a thread-local channel for each non-main thread to avoid sharing non-thread-safe
      Pika channels across threads.
    - Makes published messages persistent (delivery mode = 2) and JSON-encodes payloads.
    - Detects closed channels/connections, reconnects, and retries the publish once.

    Attributes:
        channel_creator: Factory that manages the underlying connection and creates channels.
        channel: The primary channel used by the main thread.
        _thread_local: Thread-local storage where per-thread channels are cached.
        queue_manager: Manages queue/exchange declaration and readiness checks.

    Notes:
        - Channels are not thread-safe. Each non-main thread gets its own channel.
        - Publishing retries on `pika` channel/connection errors by reconnecting and re-attempting
          the same message. Consider adding bounded retries with backoff for robustness.
    """

    def __init__(self, queue_params: QueueParams) -> None:
        """
        Initialize the producer and ensure the queue infrastructure is ready.

        :param queue_params: queue configuration object containing queue_name, exchange_name,
        exchange_type, durable, routing_key, and queue_arguments.

        Behaviour:
        - Build a ChannelCreator and opens an initial channel for the main thread.
        - Initialize thread-local storage for per-thread channels.
        - Build a QueueManager to handle queue/exchange setup.
        - Check if the queue is ready; if not, call `queue_reconnect` to set it up.

        """
        # Define credentials (user/password) as environment variables
        # declaring the credentials needed for connection like host, port, username, password, exchange etc

        # Object to create channels
        self.channel_creator = ChannelCreator(queue_params.user,
                                              queue_params.password,
                                              queue_params.host)  # Factory to create channels
        self.channel = self.channel_creator.get_channel()

        # Thread-local storage for channels (for multi-threading support)
        self._thread_local = threading.local()

        # Object to create the queue and manage its setup and attributes
        self.queue_manager = QueueManager(queue_params)

        # Ensure the queue is ready when the producer is initialized
        if not self.queue_manager.is_ready(self.channel):
            logger.warning("Queue setup not ready. Initializing channel and setup.")
            self.queue_reconnect()

    def _get_thread_channel(self):
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
        if not hasattr(self._thread_local, 'channel') or not self._thread_local.channel or self._thread_local.channel.is_closed:
            self._thread_local.channel = self.channel_creator.get_channel()
            # Set up queue for this thread's channel
            self.queue_manager.set_up_queue(self._thread_local.channel)

        return self._thread_local.channel

    def _thread_reconnect(self) -> None:
        """
        Reconnect the channel for the current thread.

        For the main thread, it calls the original `queue_reconnect`.
        For other threads, it creates a new thread-local channel and re-runs the queue set up.
        """
        if threading.current_thread() is threading.main_thread():
            # Main thread uses the original reconnect method
            self.queue_reconnect()
        else:
            # Other threads recreate their thread-local channel
            logger.info("Reconnecting thread-local channel...")
            self._thread_local.channel = self.channel_creator.get_channel()
            self.queue_manager.set_up_queue(self._thread_local.channel)

    def queue_reconnect(self) -> None:
        """
        Re-establish the RabbitMQ connection and channel and set up the queue infrastructure.
        This should be called when the connection or channel is closed unexpectedly.

        Behavior:
            - Requests a fresh channel from `channel_creator`.
            - Replaces the main-thread channel and re-declares queue/exchange/bindings.
        :return: None
        """
        logger.info("Reconnecting to RabbitMQ...")

        # Create a new channel
        new_channel = self.channel_creator.get_channel()

        # Replace the old channel with the new one
        self.channel = new_channel
        try:
            # Set up the queue again if needed
            self.queue_manager.set_up_queue(self.channel)
        except Exception as err:
            logger.error(f"Failed to reinitialize queue setup: {err}", exc_info=True)
            raise

    def publish_messages(self, queue_message: Dict[str, Any]) -> None:

        # TODO: Define a dataclass for the queue message to ensure type safety and validation
        # TODO: Define a retry mechanism with exponential backoff for publishing messages

        """
        Serialize and publish the message using thread-safe channel management.

        Behaviour:
         - If the channel is closed during publishing, it will attempt to reconnect and retry
        publishing.
         - The message is serialized to JSON format before publishing.

        :param queue_message: The message to be published should be a dictionary.
        :return: None

        :raises: Exception if the message cannot be serialized or published.
        :raises: pika.exceptions.ChannelClosed and pika.exceptions.ConnectionClosed if the channel is closed during publishing.
        :raises: pika.exceptions.ConnectionClosed if the connection is closed during publishing.
        :raises: pika.exceptions.StreamLostError if the stream is lost during publishing.
        :raises: pika.exceptions.ChannelWrongStateError if the channel is in the wrong state during publishing.
        :raises: Other exceptions that may occur during publishing.

        Notes:
            - Consider adding bounded retries with exponential backoff to avoid unbounded recursion.
        """
        message_id = get_queue_message_id(queue_message)

        # Get the appropriate channel for this thread
        channel = self._get_thread_channel()

        try:
            if not channel or channel.is_closed:
                logger.warning(f"Channel closed before publish (queue: {self.queue_manager.queue_name}). Reconnecting.")
                self._thread_reconnect()
                channel = self._get_thread_channel()

            try:
                body = json.dumps(queue_message)
            except (TypeError, ValueError) as json_err:
                logger.error(
                    f"Failed to serialize message {queue_message.get('ht_id')}: {json_err}", exc_info=True
                )
                raise

            channel.basic_publish(
                                exchange=self.queue_manager.main_exchange_name,
                                routing_key=self.queue_manager.queue_name,
                                body=body,
                                properties=pika.BasicProperties(delivery_mode=DELIVERY_MODE_PERSISTENT,
                                                                content_type="application/json")  # make a message persistent
                                )

            logger.info(f"Published message to {self.queue_manager.queue_name}. Message ID: {message_id}")

        except (pika.exceptions.ChannelClosed, pika.exceptions.ConnectionClosed,
                pika.exceptions.ChannelWrongStateError, pika.exceptions.StreamLostError) as err:
            logger.warning(f"RabbitMQ connection/channel closed while publishing: {err}. Reconnecting and retrying...")
            self._thread_reconnect()
            self.publish_messages(queue_message)  # Retry

        except Exception as err:
            logger.error(
                f"Unexpected error publishing message {queue_message.get('ht_id')}: {err}", exc_info=True
            )
            raise
