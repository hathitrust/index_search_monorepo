# consumer
import time
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Generator, Tuple

import orjson
import pika
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import FlexibleDict

from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_manager import QueueManager

logger = get_ht_logger(name=__name__)

class QueueMultipleConsumer(ABC):
    def __init__(self, user: str, password: str, host: str, config: FlexibleDict) -> None:

        """
        This class is used to consume a batch of messages from the queue
        :param user: username for the RabbitMQ
        :param password: password for the RabbitMQ
        :param host: host for the RabbitMQ
        :param config: queue configuration dictionary containing queue_name, exchange_name,
        exchange_type, durable, routing_key, and queue_arguments.

        Consumer class handles additional attributes like:
        - requeue_message: If True, messages will be requeued to the queue if processing fails, otherwise they
        will be sent to the Dead Letter Queue.
        - shutdown_on_empty_queue: If True, the consumer will stop consuming messages when the queue
        """
        self.channel_creator = ChannelCreator(user, password, host)  # Factory to create channels
        self.channel = self.channel_creator.get_channel()

        self.queue_config = config  # Configuration for the queue
        self.queue_manager = QueueManager(self.queue_config)

        # Requeue_message is a boolean to requeue the message to the queue.
        # If it is False, the message will be rejected, and it will be sent to the Dead Letter Queue.
        self.requeue_message = self.queue_config.get("requeue_message", False)
        # shutdown_on_empty_queue is a boolean to stop consuming messages when the queue is empty.
        # It is used for testing purposes.
        self.shutdown_on_empty_queue = self.queue_config.get("shutdown_on_empty_queue", False)

        # Ensure the queue is ready when the consumer is initialized
        if not self.queue_manager.is_ready(self.channel):
            logger.warning("Queue setup not ready. Initializing channel and setup.")
            # The channel will be closed if the queue doesn't exist or is declared with different options.
            # We need to set up the queue again.
            self.queue_reconnect()

    @abstractmethod
    def process_batch(self, batch: List[Any], delivery_tag: List[int]) -> None | Any:
        """ Abstract method for processing a batch of messages. Must be implemented by subclasses.

        Steps to implement on the subclass:
        Method to process the batch of messages.
        If the processing is successful, acknowledge all the messages in the batch.
        If the processing fails, requeue all the failed messages to the Dead Letter Queue.
        Clear the batch and the delivery tags lists.
        :param batch: List of messages to process.
        :param delivery_tag: List of delivery tags for acknowledging messages.
        :return: None
        """
        pass

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

    def consume_batch(self) -> None:
        
        """Consume a batch of messages from the queue and process them.        
        """

        if not self.channel or self.channel.is_closed:
            logger.warning("Queue setup not ready. Reinitializing channel and setup.")
            self.channel = self.channel_creator.get_channel()
            self.queue_reconnect()

        """ Retrieves a full batch of messages before processing """
        while True:
            batch = [] # It stores messages for batch processing
            delivery_tag = [] # It stores delivery tags for acknowledging messages
            for _ in range(self.queue_manager.batch_size):
                # Use basic_get to retrieve a batch of messages and auto_ack=False to tell RabbitMQ to not wait for
                # an acknowledgment of the message. We will manually acknowledge them
                method_frame, properties, body = self.channel.basic_get(queue=self.queue_manager.queue_name,
                                                                        auto_ack=False)
                if method_frame:
                    batch.append(body)
                    delivery_tag.append(method_frame.delivery_tag)
                else:
                    break  # Stop if no more messages in the queue

            if not batch:
                if self.shutdown_on_empty_queue:
                    logger.info("Queue is empty. Stopping consumer...")
                    return
                else:
                    time.sleep(0.5)  # Wait before checking for more messages
                    logger.info("No messages in the queue. Waiting for more messages...")
                    continue
            try:
                batch_data = [orjson.loads(body) for body in batch]
                # Process batch of messages and acknowledge them if successful
                # If the process_batch method returns False, stop consuming messages from the queue.
                # We use it for testing purposes. However, we could add a flag to the service to stop consuming messages.
                if not self.process_batch(batch_data, delivery_tag):
                    logger.info("Batch processing returned False. Stopping consumption.")
                    break

            except Exception as e:
                logger.error(f"[!] Error processing batch: {e}")
                raise e

    def consume_dead_letter_messages(self, channel: pika.adapters.blocking_connection.BlockingChannel,
                                     inactivity_timeout: int = 3, queue_name: str = '') -> Generator[Tuple[Any, Any, None], None, None]:
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

    def start_consuming(self) -> None:
        """Starts consuming messages from the queue."""
        try:
            self.consume_batch()
        except Exception as e:
            logger.error(f"Something went wrong while consuming messages. {e}")

    def reject_message(self, used_channel: pika.adapters.blocking_connection.BlockingChannel, basic_deliver: int) -> None:
        """Rejects a message and either requeues it or sends it to the Dead Letter Queue based on requeue_message flag.

        :param used_channel: The RabbitMQ channel to reject the message from
        :param basic_deliver: The delivery tag of the message to reject
        :return: None
        """
        used_channel.basic_reject(delivery_tag=basic_deliver, requeue=self.requeue_message)

    def positive_acknowledge(self, used_channel: pika.adapters.blocking_connection.BlockingChannel, delivery_tag: int) -> None:
        """Acknowledges a message as successfully processed.

        :param used_channel: The RabbitMQ channel to acknowledge the message on
        :param delivery_tag: The delivery tag of the message to acknowledge
        :return: None
        """
        used_channel.basic_ack(delivery_tag=delivery_tag)

    def stop(self) -> None:
        """Stop consuming messages
        Use this function for testing purposes only.
        """
        # TODO: To stop the services we should add shutdown_on_empty_queue flag as a class attribute and we should return False
        #         when the queue is empty on the method process_batch.
        logger.info("Time's up! Stopping consumer...")
        self.channel.close()
        self.channel_creator.connection.queue_connection.close()




