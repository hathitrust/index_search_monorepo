# producer
import json

from ht_queue_service.queue_connection import QueueConnection
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class QueueProducer:
    """ Create a class to send messages to a rabbitMQ """

    def __init__(self, user: str, password: str, host: str, queue_name: str, dead_letter_queue: bool = True):
        """

        :param user: username for the RabbitMQ
        :param password: password for the RabbitMQ
        :param host: host for the RabbitMQ
        :param queue_name: name of the queue
        :param dead_letter_queue: boolean to enable dead letter queue
        """
        # Define credentials (user/password) as environment variables
        # declaring the credentials needed for connection like host, port, username, password, exchange etc

        self.user = user
        self.host = host
        self.queue_name = queue_name
        self.password = password

        try:
            self.conn = QueueConnection(self.user, self.password, self.host, self.queue_name,
                                        dead_letter_queue=dead_letter_queue)
        except Exception as e:
            raise e

    def publish_messages(self, queue_message: dict) -> None:

        try:
            # We are using the default exchange
            # method used which we call to send messages to specific queue
            # Do we need to create a new exchange our we could use the default
            # routing_key is the name of the queue
            self.conn.ht_channel.basic_publish(exchange=self.conn.exchange,
                                               routing_key=self.queue_name,
                                               body=json.dumps(queue_message)
                                               )

            logger.info("Message was confirmed in the queue")

        # TODO - Add a better exception handling
        # pika.exceptions.ChannelWrongStateError add the method on_open_callback to check if the channel is oppened
        # https://github.com/pika/pika/issues/1240
        # pika examples: https://github.com/pika/pika/blob/main/examples/asynchronous_publisher_example.py
        except Exception as err:
            e_name = type(err).__name__
            logger.debug(f"Message {queue_message.get('ht_id')} could not be confirmed: exception = {e_name} e = {err}")
            logger.debug('Trying to reconnect to RabbitMQ in 5 seconds: %s', err)
            raise err
        finally:
            if self.conn.queue_connection:
                self.conn.queue_connection.close()
                logger.info("Connection to RabbitMQ closed")
        self.conn.queue_reconnect()
