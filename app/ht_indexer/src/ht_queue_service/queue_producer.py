# producer
import json
import pika.exceptions
from ht_queue_service.channel_factory import ChannelFactory
from ht_queue_service.queue_setup import set_up_queue
from ht_queue_service.queue_connection import QueueConnection

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class QueueProducer(QueueConnection):
    """ Create a class to send messages to a rabbitMQ """

    def __init__(self, user: str, password: str, host: str, queue_name: str,
                 batch_size: int = 1, exchange_name: str = "ht_exchange"):
        """

        :param user: username for the RabbitMQ
        :param password: password for the RabbitMQ
        :param host: host for the RabbitMQ
        :param queue_name: name of the queue
        """
        # Define credentials (user/password) as environment variables
        # declaring the credentials needed for connection like host, port, username, password, exchange etc

        # Start connection to RabbitMQ
        super().__init__(user, password, host)

        # Queue setup
        self.queue_name = queue_name
        self.exchange_name = exchange_name # Main exchange for the queue
        self.batch_size = batch_size

        #self.main_exchange = f"{exchange_name}_{queue_name}"  # Main exchange for the queue
        self.dlx_exchange = f"dlx_{self.exchange_name}"  # Dead-letter exchange
        self.exchange_type = "direct"  # Type of the exchange, can be 'direct', 'fanout', 'topic', etc.
        self.durable = True # the queue will survive a broker restart
        self.auto_delete = False # the queue won't be deleted once the consumer is disconnected
        self.queue_arguments = {'x-dead-letter-exchange': self.dlx_exchange,
                                        "x-dead-letter-routing-key": f"dlx_key_{queue_name}"}

        # Object to create channels
        self.channel_factory = ChannelFactory(self)  # Factory to create channels
        self.queue_setup = False  # Flag to check if the queue is set up

        #self.ht_channel.confirm_delivery() # Ensure the channel is in confirm mode
        #try:
        #    self.dlq_conn = QueueConnectionDeadLetter(user, password, self.host, self.queue_name, batch_size)
        #except Exception as e:
        #    logger.error(
        #        f"Failed to create dead-letter queue connection for {self.queue_name}: {e}"
        #    )
        #    raise

    def publish_messages(self, queue_message: dict, channel) -> None:
        # TODO Check if make sent to close the connection after publishing each message

        try:

            if not self.queue_setup:
                set_up_queue(channel, self.queue_name, self.exchange_name, self.dlx_exchange,
                             self.exchange_type, self.durable, self.auto_delete, self.queue_arguments, self.batch_size)
                self.queue_setup = True
                logger.info(f"Queue {self.queue_name} set up successfully.")

            # TODO: Check if the channel is closed and reconnect if necessary
            #if not self.ht_channel or self.ht_channel.is_closed:
            #    self.queue_reconnect()

            # Ensure the message is a dictionary and contains the 'ht_id' key
            try:
                body = json.dumps(queue_message)
            except (TypeError, ValueError) as json_err:
                logger.error(
                    f"Failed to serialize message {queue_message.get('ht_id')}: {json_err}", exc_info=True
                )
                raise

            channel.basic_publish(exchange=self.exchange_name,
                                  routing_key=self.queue_name,
                                  body=body,
                                  properties=pika.BasicProperties(delivery_mode=2,
                                                                  content_type="application/json") # make a message persistent
            )
            logger.info(f"Published message to {self.queue_name}: {body}")

        except (pika.exceptions.ChannelClosed, pika.exceptions.ConnectionClosed) as err:
            logger.warning(f"RabbitMQ connection/channel closed: {err}. Reconnecting...")
            # TODO: Check if the channel is closed and reconnect if necessary
            self.queue_reconnect()
            raise

        except Exception as err:
            logger.error(
                f"Failed to publish message {queue_message.get('ht_id')}: {err}", exc_info=True
            )
            raise

        #finally:
        #    if self.queue_connection and not self.queue_connection.is_closed:
        #        try:
        #            self.queue_connection.close()
        #            logger.info("RabbitMQ connection closed.")
        #        except Exception as close_err:
        #            logger.warning(f"Error closing RabbitMQ connection: {close_err}")
