# consumer
from abc import ABC, abstractmethod

import orjson
import time

from ht_queue_service.queue_connection import QueueConnection
from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_setup import QueueSetUp
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

class QueueMultipleConsumer(ABC, QueueConnection):
    def __init__(self, user: str, password: str, host: str, queue_name: str,
                 requeue_message: bool = False, batch_size: int = 1, shutdown_on_empty_queue: bool = False):

        """
        This class is used to consume a batch of messages from the queue
        :param user: username for the RabbitMQ
        :param password: password for the RabbitMQ
        :param host: host for the RabbitMQ
        :param queue_name: name of the queue
        :param requeue_message: boolean to requeue the message to the queue
        :param batch_size: size of the batch to be consumed
        :param shutdown_on_empty_queue: boolean to stop consuming messages when the queue is empty
        """

        super().__init__(user, password, host)

        # TODO - Add yml file to configure the queue parameters
        # Queue setup

        self.queue_name = queue_name
        self.main_exchange_name = f"exchange_{self.queue_name}" # Main exchange for the queue
        self.dlx_exchange = f"dlx_{self.main_exchange_name}"  # Dead-letter exchange

        self.batch_size = batch_size if batch_size else 1
        self.exchange_type = "direct"  # Type of the exchange, can be 'direct', 'fanout', 'topic', etc.
        self.durable = True # the queue will survive a broker restart
        self.auto_delete = False # the queue won't be deleted once the consumer is disconnected
        self.queue_arguments = {'x-dead-letter-exchange': self.dlx_exchange,
                                "x-dead-letter-routing-key": f"dlx_key_{queue_name}"}

        # Object to create channels
        self.channel_creator = ChannelCreator(self)  # Class to create channels
        self.channel = self.channel_creator.get_channel()
        # Object to create the queue and manage its setup and attributes
        self.queue_setup = self.create_queue_setup()
        if not self.queue_setup.is_ready():
            # The channel will be closed if the queue doesn't exist or is declared with different options.
            # We need to set up the queue again.
            #self.channel = self.channel_creator.get_channel()  # Reopen channel after exception
            logger.warning("Queue setup not ready. Initializing channel and setup.")
            self.queue_reconnect()
            self.queue_setup.set_up_queue()

        # Requeue_message is a boolean to requeue the message to the queue.
        # If it is False, the message will be rejected, and it will be sent to the Dead Letter Queue.
        self.requeue_message = requeue_message
        # shutdown_on_empty_queue is a boolean to stop consuming messages when the queue is empty.
        # It is used for testing purposes.
        self.shutdown_on_empty_queue = shutdown_on_empty_queue

    @abstractmethod
    def process_batch(self, batch: list, delivery_tag: list) -> bool:
        """ Abstract method for processing a batch of messages. Must be implemented by subclasses.

        Steps to implement on the subclass:
        Method to process the batch of messages.
        If the processing is successful, acknowledge all the messages in the batch.
        If the processing fails, requeue all the failed messages to the Dead Letter Queue.
        Clear the batch and the delivery tags lists.
        """
        pass

    def create_queue_setup(self):
        return QueueSetUp(self.channel_creator,
                          self.channel,
                          self.queue_name,
                          self.main_exchange_name,
                          self.dlx_exchange,
                          self.exchange_type,
                          self.durable,
                          self.auto_delete,
                          self.queue_arguments,
                          self.batch_size)

    def queue_reconnect(self):
        """
        Re-establish the RabbitMQ connection and channel, and set up the queue infrastructure again.
        This should be called when the connection or channel is closed unexpectedly.
        """
        logger.info("Reconnecting to RabbitMQ...")

        try:
            # Create a new channel
            new_channel = self.channel_creator.get_channel()

            # Replace the old channel with the new one
            self.channel = new_channel

            # Set up the queue again if needed
            self.queue_setup = self.create_queue_setup()

            logger.info("Reconnected and queue setup completed.")
        except Exception as err:
            logger.error("Failed to reconnect to RabbitMQ or set up queue again.", exc_info=True)
            raise

    def consume_batch(self):

        if not self.channel or self.channel.is_closed:
            logger.warning("Queue setup not ready. Reinitializing channel and setup.")
            self.channel = self.channel_creator.get_channel()
            self.queue_reconnect()
        #if not self.queue_setup.is_ready():
            # The channel will be closed if the queue doesn't exist or is declared with different options.
            # We need to set up the queue again.
            #self.channel = self.channel_creator.get_channel()   # Reopen channel after exception
        #    self.queue_reconnect()
        #    self.queue_setup.set_up_queue()

        """ Retrieves a full batch of messages before processing """
        while True:
            batch = [] # It stores messages for batch processing
            delivery_tag = [] # It stores delivery tags for acknowledging messages
            for _ in range(self.queue_setup.batch_size):
                # Use basic_get to retrieve a batch of messages and auto_ack=False to tell RabbitMQ to not wait for
                # an acknowledgment of the message. We will manually acknowledge them
                method_frame, properties, body = self.channel.basic_get(queue=self.queue_setup.queue_name, auto_ack=False)
                if method_frame:
                    batch.append(body)
                    delivery_tag.append(method_frame.delivery_tag)
                else:
                    break  # Stop if no more messages in the queue

            # long-polling is used to wait for messages in the queue
            #if not batch and not self.shutdown_on_empty_queue:
                #time.sleep(2)  # Avoid busy looping
            #    continue
            # If the batch is empty and shutdown_on_empty_queue is True, stop consuming messages.
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

    def consume_dead_letter_messages(self, channel, inactivity_timeout: int = None, queue_name: str = None) -> dict or None:
        """
        This method consumes messages from the queue.
        : param inactivity_timeout: time in seconds to wait for a message before returning None

        :return: a generator that yields a dictionary with the method_frame, properties, and body of the message.
        Always ask if method_frame is None when you use this function
        We use channel.consume() to consume messages from the queue.
        RabbitMQ registers the process, creating a consumer tag as an identifier for the consumer.
        This register is active until you cancel the consumer or close the channel/connection,
        Add a finally block to close the connection.
        """
        # Inactivity timeout is the time in seconds to wait for a message before returning None, the consumer will
        try:

            if not self.queue_setup.is_ready():

                # The channel will be closed if the queue doesn't exist or is declared with different options.
                # We need to set up the queue again.
                # channel = self.channel_creator.get_channel()   # Reopen channel after exception
                self.queue_reconnect()
                self.queue_setup.set_up_queue()
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

    def start_consuming(self):
        """Starts consuming messages from the queue."""
        try:
            #consumer_channel = self.channel_factory.get_channel()
            self.consume_batch()
        except Exception as e:
            logger.error(f"Something went wrong while consuming messages. {e}")

    def reject_message(self, used_channel, basic_deliver):
        used_channel.basic_reject(delivery_tag=basic_deliver, requeue=self.requeue_message)

    def positive_acknowledge(self, used_channel, delivery_tag):
        used_channel.basic_ack(delivery_tag=delivery_tag)

    def stop(self):
        """Stop consuming messages
        Use this function for testing purposes only.
        """
        # TODO: To stop the services we should add shutdown_on_empty_queue flag as a class attribute and we should return False
        #         when the queue is empty on the method process_batch.
        logger.info("Time's up! Stopping consumer...")
        self.channel.close()
        self.queue_connection.close()




