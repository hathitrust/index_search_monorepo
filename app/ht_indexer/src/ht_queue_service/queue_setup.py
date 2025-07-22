from pika.exceptions import ChannelClosedByBroker

from ht_queue_service.channel_creator import ChannelCreator
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


"""
    We use a dead-letter-exchange to handle messages that are not processed successfully.
    The dead-letter-exchange is an exchange to which messages will be re-routed if they are rejected by the queue.
    See a detail explanation of dead letter exchanges here: https://www.rabbitmq.com/docs/dlx#overview
    A message is dead-lettered if it is negatively acknowledged and requeued, or if it times out.
    """
# TODO - Create a class that manages the queue setup, exchange, and dead letter exchange
# TODO - Rename this class to QueueSetUp
# TODO - Create a method to close the connection and channel after the queue setup is done
# TODO - Create a method  is_ready to use in the producer and consumer to check if the queue is set up

class QueueSetUp:
    """
    Class to set up a queue in RabbitMQ with a dead-letter exchange.
    It declares the main exchange, the dead-letter exchange, and the main queue.
    It also binds the dead-letter exchange to the dead-letter queue.
    """

    def __init__(self, channel_creator: ChannelCreator, channel, queue_name, exchange_name, dlx_exchange,
                 exchange_type='direct', durable=True, auto_delete=False, queue_arguments=None, batch_size=1):
        self.channel_creator = channel_creator
        self.channel = channel
        self.queue_name = queue_name
        self.main_exchange_name = exchange_name
        self.dlx_exchange = dlx_exchange
        self.exchange_type = exchange_type
        self.durable = durable
        self.auto_delete = auto_delete
        self.queue_arguments = queue_arguments or {
            'x-dead-letter-exchange': dlx_exchange,
            'x-dead-letter-routing-key': f"dlx_key_{queue_name}"
        }
        self.batch_size = batch_size

    def is_ready(self) -> bool:

        """
        Check if a queue exists in RabbitMQ.
        :return: True if the queue exists, False otherwise.
        IMPORTANT: The channel will be closed if the queue doesn't exist — I must open a new one.
        """
        try:
            self.channel.queue_declare(queue=self.queue_name, passive=True)
            logger.info(f"Queue {self.queue_name} exists.")
            return True
        except ChannelClosedByBroker:
            # Queue doesn't exist or is declared with different options
            # TODO Check what happend with the channel here!!!!
            logger.info(f"Queue {self.queue_name} does not exist.")
            return False

    def set_up_queue(self) -> bool:

        """
        Create the exchange, dead-letter exchange, and queue in RabbitMQ if they do not exist.

        :param channel_creator: The ChannelCreator instance to create a new channel if needed.
        :param channel: The RabbitMQ channel to set up the queue on.
            channel - a channel is a virtual connection inside a connection
        :param queue_name: The name of the queue to set up.
            queue a name is important when you want to share the queue between producers and consumers
        :param exchange_name: The name of the main exchange to declare.
        :param dlx_exchange: The name of the dead-letter exchange to declare.
        :param exchange_type: The type of the exchange (default is 'direct').
        :param durable: Whether the queue and exchanges are durable (default is True).
            durable=True - the queue will survive a broker restart
        :param auto_delete: Whether the queue and exchanges are auto-deleted (default is False)
            auto_delete=False - the queue won't be deleted once the consumer is disconnected
        :param queue_arguments: Additional arguments for the queue, such as dead-letter exchange and routing key.
            arguments - the dead-letter-exchange and dead-letter-routing-key are used to define the dead letter exchange
            and the routing key to use when a message is dead-lettered
        :param batch_size: The maximum number of unacknowledged deliveries that are permitted on
        the channel (default is 1).
        :return: True if the queue was set up successfully, False otherwise.
        :raises ChannelClosedByBroker: If the queue does not exist or is declared with different options.
        """

        if not self.channel:
            logger.error("Channel was None, so  a new channel has been created to set up the queue.")
            self.channel = self.channel_creator.get_channel()

        # Declare the main exchange
        self.channel.exchange_declare(self.main_exchange_name,
                                      exchange_type=self.exchange_type,
                                      durable=self.durable,
                                      auto_delete=self.auto_delete)

        # Declare the dead letter exchange
        self.channel.exchange_declare(self.dlx_exchange,
                                 exchange_type=self.exchange_type,
                                 durable=self.durable,
                                 auto_delete=self.auto_delete)

        # Declare the main queue
        # exclusive=False - the queue can be accessed in other channels
        self.channel.queue_declare(queue=self.queue_name,
                              durable=self.durable,
                              exclusive=False,
                              auto_delete=self.auto_delete,
                              arguments=self.queue_arguments)

        # Declare the dead letter queue
        self.channel.queue_declare(f"{self.queue_name}_dlq")

        # Bind the dead letter exchange to the dead letter queue
        # The queue_bind method binds a queue to an exchange. The queue will now receive messages from the exchange,
        # Otherwise, no messages will be routed to the queue.
        self.channel.queue_bind(f"{self.queue_name}_dlq", self.dlx_exchange, f"dlx_key_{self.queue_name}")

        # The relationship between exchange and a queue is called a binding.
        # Link the exchange to the queue to send messages.
        self.channel.queue_bind(self.queue_name, self.main_exchange_name, routing_key=self.queue_name)

        # The value defines the maximum number of unacknowledged deliveries that are permitted on a channel.
        # When the number reaches the configured count, RabbitMQ will stop delivering more messages on the
        # channel until at least one of the outstanding ones is acknowledged.
        self.channel.basic_qos(prefetch_count=self.batch_size)

        logger.info(f"Queue {self.queue_name} set up successfully with exchange {self.main_exchange_name} "
                    f"and DLX {self.dlx_exchange}.")
        return True


