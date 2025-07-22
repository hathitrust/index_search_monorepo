# producer
import json

import pika.exceptions
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import FlexibleDict, get_queue_message_id

from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_manager import QueueManager

logger = get_ht_logger(name=__name__)

class QueueProducer:
    """ Create a class to send messages to a rabbitMQ """

    # TODO: Load queue configuration from a config file or environment variables

    def __init__(self, user: str, password: str, host: str, config: FlexibleDict) -> None:
        """

        :param user: username for the RabbitMQ
        :param password: password for the RabbitMQ
        :param host: host for the RabbitMQ
        :param config: queue configuration dictionary containing queue_name, exchange_name,
        exchange_type, durable, routing_key, and queue_arguments.
        """
        # Define credentials (user/password) as environment variables
        # declaring the credentials needed for connection like host, port, username, password, exchange etc

        # Object to create channels
        self.channel_creator = ChannelCreator(user, password, host)  # Factory to create channels
        self.channel = self.channel_creator.get_channel()

        self.queue_config = config  # Configuration for the queue

        # Object to create the queue and manage its setup and attributes
        self.queue_manager = QueueManager(self.queue_config)

        # Ensure the queue is ready when the producer is initialized
        if not self.queue_manager.is_ready(self.channel):
            logger.warning("Queue setup not ready. Initializing channel and setup.")
            self.queue_reconnect()

    def queue_reconnect(self) -> None:
        """
        Re-establish the RabbitMQ connection and channel and set up the queue infrastructure.
        This should be called when the connection or channel is closed unexpectedly.

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

    def publish_messages(self, queue_message: FlexibleDict) -> None:

        # TODO: Define a dataclass for the queue message to ensure type safety and validation

        """
        Publish the message. If the channel is closed during publishing, it will attempt to reconnect and retry
        publishing. The message is serialized to JSON format before publishing.
        :param queue_message: The message to be published, should be a dictionary.
        :return: None

        :raises: Exception if the message cannot be serialized or published.
        :raises: pika.exceptions.ChannelClosed and pika.exceptions.ConnectionClosed if the channel is closed during publishing.
        :raises: pika.exceptions.ConnectionClosed if the connection is closed during publishing.
        :raises: pika.exceptions.StreamLostError if the stream is lost during publishing.
        :raises: pika.exceptions.ChannelWrongStateError if the channel is in the wrong state during publishing.
        :raises: Other exceptions that may occur during publishing.
        """

        try:

            if not self.channel or self.channel.is_closed:

                logger.warning("Queue setup not ready. Reinitializing channel and setup.")
                self.channel = self.channel_creator.get_channel()   # Reopen channel after exception
                self.queue_reconnect()

            try:
                body = json.dumps(queue_message)
            except (TypeError, ValueError) as json_err:
                logger.error(
                    f"Failed to serialize message {queue_message.get('ht_id')}: {json_err}", exc_info=True
                )
                raise

            if not self.channel or self.channel.is_closed:
                logger.warning("Channel is closed before publish. Reconnecting.")
                self.queue_reconnect()
                raise pika.exceptions.ChannelClosed("Channel was closed")

            self.channel.basic_publish(exchange=self.queue_manager.main_exchange_name,
                                  routing_key=self.queue_manager.queue_name,
                                  body=body,
                                  properties=pika.BasicProperties(delivery_mode=2,
                                                                  content_type="application/json")  # make a message persistent
                                  )
            message_id = get_queue_message_id(queue_message)
            logger.info(f"Published message to {self.queue_manager.queue_name}. Message ID: {message_id}")

        except (pika.exceptions.ChannelClosed, pika.exceptions.ConnectionClosed,
                pika.exceptions.ChannelWrongStateError, pika.exceptions.StreamLostError) as err:
            logger.warning(f"RabbitMQ connection/channel closed while publishing: {err}. Reconnecting and retrying...")
            self.queue_reconnect()
            self.publish_messages(queue_message)

        except Exception as err:
            logger.error(
                f"Failed to publish message {queue_message.get('ht_id')}: {err}", exc_info=True
            )
            raise
