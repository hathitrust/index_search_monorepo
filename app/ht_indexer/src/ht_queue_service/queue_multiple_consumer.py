# consumer
from abc import ABC, abstractmethod

import orjson
from ht_utils.ht_logger import get_ht_logger

from ht_queue_service.queue_connection import QueueConnection
from ht_queue_service.queue_connection_dead_letter import QueueConnectionDeadLetter

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
        """

        super().__init__(user, password, host, queue_name, batch_size if batch_size else 1)
        self.requeue_message = requeue_message

        # Requeue_message is a boolean to requeue the message to the queue.
        # If it is False, the message will be rejected, and it will be sent to the Dead Letter Queue.
        self.requeue_message = requeue_message
        # shutdown_on_empty_queue is a boolean to stop consuming messages when the queue is empty.
        # It is used for testing purposes.
        self.shutdown_on_empty_queue = shutdown_on_empty_queue

        try:
            self.dlq_conn = QueueConnectionDeadLetter(self.user, self.password, self.host, self.queue_name, batch_size)
        except Exception as e:
            raise e

    @abstractmethod
    def process_batch(self, batch: list, delivery_tag: list):
        """ Abstract method for processing a batch of messages. Must be implemented by subclasses.

        Steps to implement on the subclass:
        Method to process the batch of messages.
        If the processing is successful, acknowledge all the messages in the batch.
        If the processing fails, requeue all the failed messages to the Dead Letter Queue.
        Clear the batch and the delivery tags lists.
        """
        pass

    def consume_batch(self):

        """ Retrieves a full batch of messages before processing """
        while True:
            batch = [] # It stores messages for batch processing
            delivery_tag = [] # It stores delivery tags for acknowledging messages
            for _ in range(self.batch_size):
                # Use basic_get to retrieve a batch of messages and auto_ack=False to tell RabbitMQ to not wait for
                # an acknowledgment of the message.We will manually acknowledge them
                method_frame, properties, body = self.ht_channel.basic_get(queue=self.queue_name,
                                                                                            auto_ack=False)
                if method_frame:
                    batch.append(body)
                    delivery_tag.append(method_frame.delivery_tag)
                else:
                    break  # Stop if no more messages in the queue

            # long-polling is used to wait for messages in the queue
            if not batch and not self.shutdown_on_empty_queue:
                #time.sleep(2)  # Avoid busy looping
                continue
            # If the batch is empty and shutdown_on_empty_queue is True, stop consuming messages.
            if not batch and self.shutdown_on_empty_queue:
                logger.info("Queue is empty. Stopping consumer...")
                return

            try:
                batch_data = [orjson.loads(body) for body in batch]
                # Process batch of messages and acknowledge them if successful
                # If the process_batch method returns False, stop consuming messages from the queue.
                # We use it for testing purposes. However, we could add a flag to the service to stop consuming messages.
                if not self.process_batch(batch_data, delivery_tag):
                    break

            except Exception as e:
                logger.error(f"[!] Error processing batch: {e}")
                raise e

    def start_consuming(self):
        """Starts consuming messages from the queue."""
        try:
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
        self.ht_channel.close()




