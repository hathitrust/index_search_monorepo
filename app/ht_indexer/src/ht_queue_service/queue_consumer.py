# consumer
from ht_utils.ht_logger import get_ht_logger

from ht_queue_service.queue_connection import QueueConnection
from ht_queue_service.queue_connection_dead_letter import QueueConnectionDeadLetter

logger = get_ht_logger(name=__name__)

class QueueConsumer(QueueConnection):
    def __init__(self, user: str, password: str, host: str, queue_name: str,
                 requeue_message: bool = False, batch_size: int = None):

        """
        This class is used to consume messages from the queue
        : param user: username for the RabbitMQ
        : param password: password for the RabbitMQ
        : param host: host for the RabbitMQ
        : param queue_name: name of the queue
        : param requeue_message: boolean to requeue the message to the queue
        : param batch_size: size of the batch to be consumed
        """

        super().__init__(user, password, host, queue_name, batch_size if batch_size else 1)
        self.requeue_message = requeue_message

    def consume_message(self, inactivity_timeout: int = None) -> dict or None:
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
            for method_frame, properties, body in self.ht_channel.consume(self.queue_name,
                                                                               auto_ack=False,
                                                                               inactivity_timeout=inactivity_timeout
                                                                               ):
                if method_frame:
                    yield method_frame, properties, body
                else:
                    yield None, None, None

        except Exception as e:
            logger.error(f"Connection Interrupted: {e}")
            raise e

    def reject_message(self, used_channel, basic_deliver):
        used_channel.basic_reject(delivery_tag=basic_deliver, requeue=self.requeue_message)

    def positive_acknowledge(self, used_channel, basic_deliver):
        used_channel.basic_ack(delivery_tag=basic_deliver)

