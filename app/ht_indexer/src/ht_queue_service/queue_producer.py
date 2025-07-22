# producer
import json
import pika.exceptions
from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_setup import QueueSetUp
from ht_queue_service.queue_connection import QueueConnection

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class QueueProducer(QueueConnection):
    """ Create a class to send messages to a rabbitMQ """

    def __init__(self, user: str, password: str, host: str, queue_name: str,
                 batch_size: int = 1):
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
        self.main_exchange_name = f"exchange_{self.queue_name}" #exchange_name # Main exchange for the queue
        self.batch_size = batch_size

        #self.main_exchange = f"{exchange_name}_{queue_name}"  # Main exchange for the queue
        self.dlx_exchange = f"dlx_{self.main_exchange_name}"  # Dead-letter exchange
        self.exchange_type = "direct"  # Type of the exchange, can be 'direct', 'fanout', 'topic', etc.
        self.durable = True # the queue will survive a broker restart
        self.auto_delete = False # the queue won't be deleted once the consumer is disconnected
        self.queue_arguments = {'x-dead-letter-exchange': self.dlx_exchange,
                                        "x-dead-letter-routing-key": f"dlx_key_{queue_name}"}

        # Object to create channels
        self.channel_creator = ChannelCreator(self)  # Factory to create channels
        self.channel = self.channel_creator.get_channel()

        self.queue_setup = self.create_queue_setup()
        # Object to create the queue and manage its setup and attributes
        # Ensure queue is ready when the producer is initialized
        if not self.queue_setup.is_ready():
            # The channel will be closed if the queue doesn't exist or is declared with different options.
            # We need to set up the queue again.
            #self.channel = self.channel_creator.get_channel()  # Reopen channel after exception
            logger.warning("Queue setup not ready. Initializing channel and setup.")
            self.queue_reconnect()
            self.queue_setup.set_up_queue()

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

    def publish_messages(self, queue_message: dict) -> None:
        # TODO Check if make sent to close the connection after publishing each message

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

            self.channel.basic_publish(exchange=self.queue_setup.main_exchange_name,
                                  routing_key=self.queue_setup.queue_name,
                                  body=body,
                                  properties=pika.BasicProperties(delivery_mode=2,
                                                                  content_type="application/json")  # make a message persistent
                                  )
            logger.info(f"Published message to {self.queue_setup.queue_name}: {body}")

        # TODO Check if we should retrying the basic_publish method
        except (pika.exceptions.ChannelClosed, pika.exceptions.ConnectionClosed,
                pika.exceptions.ChannelWrongStateError, pika.exceptions.StreamLostError) as err:
            logger.warning(f"RabbitMQ connection/channel closed: {err}. Reconnecting and retrying...")
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


