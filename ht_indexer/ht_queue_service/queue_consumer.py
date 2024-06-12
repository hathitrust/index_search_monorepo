# consumer
from ht_queue_service.queue_connection_dead_letter import QueueConnectionDeadLetter
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


def positive_acknowledge(used_channel, basic_deliver):
    used_channel.basic_ack(delivery_tag=basic_deliver)


class QueueConsumer:
    def __init__(self, user: str, password: str, host: str, queue_name: str,
                 requeue_message: bool = False):

        """
        This class is used to consume messages from the queue
        :param user: username for the RabbitMQ
        :param password: password for the RabbitMQ
        :param host: host for the RabbitMQ
        :param queue_name: name of the queue
        :param requeue_message: boolean to requeue the message to the queue
        """

        # Credentials (user/password) are defined as environment variables
        # declaring the credentials needed for connection like host, port, username, password, exchange etc.
        self.user = user
        self.host = host
        self.queue_name = queue_name
        self.password = password
        self.requeue_message = requeue_message

        try:
            self.conn = QueueConnectionDeadLetter(self.user, self.password, self.host, self.queue_name)
        except Exception as e:
            raise e

    def consume_message(self, inactivity_timeout: int = None) -> dict:

        # Inactivity timeout is the time in seconds to wait for a message before returning None, the consumer will
        try:
            for method_frame, properties, body in self.conn.ht_channel.consume(self.queue_name,
                                                                               auto_ack=False,
                                                                               inactivity_timeout=inactivity_timeout
                                                                               ):
                if method_frame:
                    yield method_frame, properties, body
                else:
                    yield None, None, None
        except Exception as e:
            logger.error(f'Connection Interrupted: {e}')
            raise e

    def reject_message(self, used_channel, basic_deliver):
        used_channel.basic_reject(delivery_tag=basic_deliver, requeue=self.requeue_message)
