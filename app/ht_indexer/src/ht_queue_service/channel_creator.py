import threading
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import ChannelClosed, ChannelClosedByBroker, ChannelWrongStateError, NoFreeChannels, AMQPError
from ht_utils.ht_logger import get_ht_logger

from ht_queue_service.queue_connection import QueueConnection

logger = get_ht_logger(name=__name__)

class ChannelCreator:

    """
    Class for creating RabbitMQ channels from a shared connection (pika.BlockingConnection) in a thread-safe manner.

    Behaviour:
        - This class ensures that multiple threads can safely create channels from the same connection.
        - It uses a threading.lock to synchronize access to the connection when creating channels.
    """

    def __init__(self, user: str, password: str, host: str):
        # TODO: Implement retry logic with exponential backoff for establishing the connection
        self.connection = QueueConnection(user, password, host) # The connection to RabbitMQ

        # Thread-safe channel creation for multi-threaded environments
        self._channel_lock = threading.Lock()

    def get_channel(self) -> BlockingChannel | None:
        """
        Create a thread-safe channel to RabbitMQ.
        This method checks if the connection is established and creates a channel.
        Multiple threads can safely call this method simultaneously.
        If the connection is not established or closed, it logs an error and returns None.
        :return: A pika channel object if successful, None otherwise.
        :raises RuntimeError: If there is an unexpected error during channel creation.
        """

        with self._channel_lock:
            try:
                # Checking connection status before creating a channel (thread-safe)
                if not self.connection or not self.connection.queue_connection or self.connection.queue_connection.is_closed:
                    logger.error("RabbitMQ connection is not established or is closed.")
                    return None
                else:
                    # Create channel from the shared connection (thread-safe)
                    channel = self.connection.queue_connection.channel()
                    logger.info("Channel created successfully.")
                    return channel
            except (ChannelClosed, ChannelClosedByBroker, ChannelWrongStateError, NoFreeChannels,
                    AMQPError, Exception) as err:
                    logger.error(f"Failed to create channel: {err}", exc_info=True)
                    raise RuntimeError(f"Failed to create channel: {err}") from err
