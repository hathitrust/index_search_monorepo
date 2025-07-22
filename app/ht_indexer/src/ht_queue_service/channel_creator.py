import pika
from ht_utils.ht_errors import HTError
from ht_utils.ht_logger import get_ht_logger

from ht_queue_service.queue_connection import QueueConnection

logger = get_ht_logger(name=__name__)

class ChannelCreator:
    def __init__(self, user: str, password: str, host: str):
        # TODO: Implement retry logic with exponential backoff for establishing the connection
        # TODO: Implement a mechanism to create thread-safe channels to use in the retriever_service multi-threaded environment
        self.connection = QueueConnection(user, password, host) # The connection to RabbitMQ

    def get_channel(self) -> pika.adapters.blocking_connection.BlockingChannel | None:
        """
        Create a channel to RabbitMQ.
        This method checks if the connection is established and creates a channel.
        If the connection is not established or closed, it logs an error and returns None.
        :return: A pika channel object if successful, None otherwise.
        :raises HTError: If there is an unexpected error during channel creation.
        """

        try:
            # Checking connection status before creating a channel
            if not self.connection or not self.connection.queue_connection or self.connection.queue_connection.is_closed:
                logger.error("RabbitMQ connection is not established or is closed.")
            else:
                channel = self.connection.queue_connection.channel()
                logger.info("Channel created successfully.")
                return channel
        except pika.exceptions.ChannelClosed as e:
            logger.error(f"Error creating RabbitMQ channel: {e}")
        except pika.exceptions.ChannelClosedByBroker as e:
            logger.error(f"Broker closed the channel: {e}")
        except pika.exceptions.ChannelWrongStateError as e:
            logger.error(f"Channel is in the wrong state: {e}")
        except pika.exceptions.NoFreeChannels as e:
            logger.error(f"No free channels available: {e}")
        except pika.exceptions.AMQPError as e:
            logger.error(f"AMQP error while setting up queue: {e}")
        except Exception as e:
            raise HTError(f"Unexpected error during queue setup: {e}") from e
        return None