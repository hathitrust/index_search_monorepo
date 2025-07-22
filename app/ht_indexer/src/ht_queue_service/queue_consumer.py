# consumer
from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_setup import QueueSetUp
from ht_queue_service.queue_connection import QueueConnection

from ht_utils.ht_logger import get_ht_logger

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

        super().__init__(user, password, host)
        self.requeue_message = requeue_message

        # Queue setup
        self.queue_name = queue_name
        self.main_exchange_name = f"exchange_{self.queue_name}" #exchange_name # Main exchange for the queue
        self.batch_size = batch_size if batch_size else 1

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
        # Object to create the queue and manage its setup and attributes
        self.queue_setup = self.create_queue_setup()
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

            if not self.channel or self.channel.is_closed:
                logger.warning("Queue setup not ready. Reinitializing channel and setup.")
                self.channel = self.channel_creator.get_channel()
                self.queue_reconnect()

            for method_frame, properties, body in self.channel.consume(self.queue_setup.queue_name,
                                                                 auto_ack=False,
                                                                 inactivity_timeout=inactivity_timeout):
                if method_frame:
                    yield method_frame, properties, body
                else:
                    yield None, None, None

        except Exception as e:
            logger.error(f"Connection Interrupted: {e}")
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

            if not self.queue_setup:
                #set_up_queue(channel, self.queue_name, self.exchange_name, self.dlx_exchange,
                #             self.exchange_type, self.durable, self.auto_delete, self.queue_arguments, self.batch_size)
                #self.queue_setup = True
                #logger.info(f"Your queue must to be set up.")
                raise Exception(f"Your queue must to be set up.")

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

    def reject_message(self, used_channel, basic_deliver):
        used_channel.basic_reject(delivery_tag=basic_deliver, requeue=self.requeue_message)

    def positive_acknowledge(self, used_channel, basic_deliver):
        used_channel.basic_ack(delivery_tag=basic_deliver)

