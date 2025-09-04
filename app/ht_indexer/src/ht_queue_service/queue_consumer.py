from collections.abc import Generator
from typing import Any

import pika
from ht_utils.ht_logger import get_ht_logger

from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_config import QueueParams
from ht_queue_service.queue_manager import QueueManager

logger = get_ht_logger(name=__name__)

class QueueConsumer:
    def __init__(self, queue_params: QueueParams) -> None:
        """
        This class is used to consume messages from the queue
        :param queue_config: queue configuration object containing queue_name, exchange_name,
        exchange_type, durable, routing_key, and queue_arguments.
        """


        self.channel_creator = ChannelCreator(queue_params.user,
                                              queue_params.password,
                                              queue_params.host)  # Factory to create channels
        self.channel = self.channel_creator.get_channel()

        self.queue_manager = QueueManager(queue_params)

        # Requeue_message is a boolean to requeue the message to the queue.
        # If it is False, the message will be rejected, and it will be sent to the Dead Letter Queue.
        self.requeue_message = queue_params.requeue_message

        # Ensure the queue is ready when the consumer is initialized
        if not self.queue_manager.is_ready(self.channel):
            logger.warning("Queue setup not ready. Initializing channel and setup.")
            # The channel will be closed if the queue doesn't exist or is declared with different options.
            # We need to set up the queue again.
            self.queue_reconnect()


    def queue_reconnect(self) -> None:
        """
        Re-establish the RabbitMQ connection and channel, and set up the queue infrastructure again.
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
            logger.error(f"Failed to reinitialize to queue set up: {err}.", exc_info=True)
            raise

    def consume_message(self, inactivity_timeout: int = 5) -> Generator[tuple[Any, Any, None], None, None]:
        """
        This method consumes messages from the queue.
        : param inactivity_timeout: time in seconds to wait for a message before returning None

        :return: a generator that yields a dictionary with the method_frame, properties, and body of the message.
        Always ask if method_frame is None when you use this function
        We use channel.consume() to consume messages from the queue.
        RabbitMQ registers the process, creating a consumer tag as an identifier for the consumer.
        This register is active until you cancel the consumer or close the channel/connection,
        Add a finally block to close the connection.
        Inactivity timeout is the time in seconds to wait for a message before returning None, the consumer will
        """
        try:
            if not self.channel or self.channel.is_closed:
                logger.warning("Queue setup not ready. Reinitializing channel and setup.")
                self.channel = self.channel_creator.get_channel()
                self.queue_reconnect()

            for method_frame, properties, body in self.channel.consume(self.queue_manager.queue_name,
                                                                 auto_ack=False,
                                                                 inactivity_timeout=inactivity_timeout):
                if method_frame:
                    yield method_frame, properties, body
                else:
                    yield None, None, None

        except Exception as e:
            logger.error(f"Connection Interrupted: {e}")
            raise e

    def consume_dead_letter_messages(self, channel: pika.adapters.blocking_connection.BlockingChannel,
                                     inactivity_timeout: int = 5, queue_name: str = '') -> Generator[tuple[Any, Any, None], None, None]:
        """
        This method consumes messages from the queue.
        :param channel: The RabbitMQ channel to consume messages from.
        :param inactivity_timeout: time in seconds to wait for a message before returning None
        :param queue_name: The name of the queue to consume messages from. If None, it will use the queue name from the configuration.
        :raises Exception: If there is an error while consuming messages.
        :return: a generator that yields a dictionary with the method_frame, properties, and body of the message.
        Always ask if method_frame is None when you use this function
        We use channel.consume() to consume messages from the queue.
        RabbitMQ registers the process, creating a consumer tag as an identifier for the consumer.
        This register is active until you cancel the consumer or close the channel/connection.
        Inactivity timeout is the time in seconds to wait for a message before returning None, the consumer will
        """

        try:

            if not self.channel or self.channel.is_closed:
                logger.warning("Queue setup not ready. Reinitializing channel and setup.")
                self.channel = self.channel_creator.get_channel()
                self.queue_reconnect()

            for method_frame, properties, body in channel.consume(queue_name,
                                                                  auto_ack=False,
                                                                  inactivity_timeout=inactivity_timeout):
                if method_frame:
                    yield method_frame, properties, body
                else:
                    yield None, None, None

        except Exception as e:
            logger.error(f"Connection Interrupted: {e}")
            raise e

    def reject_message(self, used_channel: pika.adapters.blocking_connection.BlockingChannel, basic_deliver: int) -> None:
        """
        Rejects a message and either requeues it or sends it to the Dead Letter Queue based on requeue_message flag.
        :param used_channel: The RabbitMQ channel to reject the message from
        :param basic_deliver: The delivery tag of the message to reject
        :return: None
        """
        used_channel.basic_reject(delivery_tag=basic_deliver, requeue=self.requeue_message)

    def positive_acknowledge(self, used_channel: pika.adapters.blocking_connection.BlockingChannel,
                             basic_deliver: int) -> None:
        """
        Acknowledges a message as successfully processed.
        :param used_channel: The RabbitMQ channel to acknowledge the message on
        :param basic_deliver: The delivery tag of the message to acknowledge
        :return: None
        """
        used_channel.basic_ack(delivery_tag=basic_deliver)

