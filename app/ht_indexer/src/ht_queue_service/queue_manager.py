from typing import Any

import pika
from ht_utils.ht_logger import get_ht_logger
from pika.channel import Channel
from pika.exceptions import ChannelClosedByBroker

from ht_queue_service.queue_config import QueueParams

logger = get_ht_logger(name=__name__)

class QueueManager:
    """
    Reusable class to manage the setup of a queue in RabbitMQ with a dead-letter exchange.
    """

    def __init__(self, queue_params: QueueParams):

        """
        Parameters for the queue setup:
        * queue_name: The name of the queue to set up. The name is important when you want to share the queue
        between producers and consumers
        * exchange_name: The name of the main exchange to declare.
        * dlx_exchange: The name of the dead-letter exchange to declare.
        * exchange_type: The type of the exchange (default is 'direct').
        * durable: Whether the queue and exchanges are durable (default is True).
            durable=True - the queue will survive a broker restart
        * auto_delete: Whether the queue and exchanges are auto-deleted (default is False)
            auto_delete=False - the queue won't be deleted once the consumer is disconnected
        * arguments: Additional arguments for the queue, such as dead-letter exchange and routing key.
            the dead-letter-exchange and dead-letter-routing-key are used to define the dead letter exchange
            and the routing key to use when a message is dead-lettered
        * batch_size: The maximum number of unacknowledged deliveries that are permitted on
        the channel (default is 1).

        """

        self.queue_name = queue_params.queue_name
        self.main_exchange_name = queue_params.main_exchange_name
        self.dlx_exchange = queue_params.dlx_exchange
        self.exchange_type = queue_params.exchange_type
        self.durable = queue_params.durable
        self.auto_delete = queue_params.auto_delete
        self.arguments = queue_params.arguments

        self.batch_size = queue_params.batch_size
        self.dead_letter_queue_name = queue_params.dlx_queue_name



    def is_ready(self, channel: Channel=None) -> bool:

        """
        Check if a queue exists in RabbitMQ.
        :return: True if the queue exists, False otherwise.
        IMPORTANT: The channel will be closed if the queue doesn't exist or is declared with different options.
        — I must open a new one.
        """
        ch = channel
        try:
            ch.queue_declare(queue=self.queue_name, durable=self.durable, passive=True)
            logger.info(f"Queue {self.queue_name} exists.")
            return True
        except ChannelClosedByBroker as e:
            # Queue doesn't exist or is declared with different options
            # TODO Check what happened with the channel here!!!!
            logger.warning(f"Queue {self.queue_name} not ready or misconfigured: {e}")
            return False

    def set_up_queue(self, channel: Channel=None) -> None:

        """
        Create the exchange, dead-letter exchange, and queue in RabbitMQ if they do not exist.

        We use a dead-letter-exchange to handle messages that are not processed successfully.
        The dead-letter-exchange is an exchange to which messages will be re-routed if the queue rejects them.
        See a detail explanation of dead letter exchanges here: https://www.rabbitmq.com/docs/dlx#overview
        A message is dead-lettered if it is negatively acknowledged and requeued, or if it times out.


        :param channel: The RabbitMQ channel to set up the queue on.
        : note: channel - a channel is a virtual connection inside a connection
        :return: None.
        :raises ChannelClosedByBroker: If the queue does not exist or is declared with different options.
        """

        ch = channel

        # Declare the main exchange
        ch.exchange_declare(self.main_exchange_name,
                                      exchange_type=self.exchange_type,
                                      durable=self.durable,
                                      auto_delete=self.auto_delete)

        # Declare the dead letter exchange
        ch.exchange_declare(self.dlx_exchange,
                                 exchange_type=self.exchange_type,
                                 durable=self.durable,
                                 auto_delete=self.auto_delete)

        # Declare the dead letter queue
        ch.queue_declare(self.dead_letter_queue_name)

        # Declare the main queue
        # exclusive=False - the queue can be accessed in other channels
        ch.queue_declare(queue=self.queue_name,
                              durable=self.durable,
                              exclusive=False,
                              auto_delete=self.auto_delete,
                              arguments=self.arguments)

        # Bind the dead letter exchange to the dead letter queue
        # The queue_bind method binds a queue to an exchange. The queue will now receive messages from the exchange,
        # Otherwise, no messages will be routed to the queue.
        ch.queue_bind(self.dead_letter_queue_name, self.dlx_exchange, self.arguments["x-dead-letter-routing-key"])

        # The relationship between exchange and a queue is called a binding.
        # Link the exchange to the queue to send messages.
        ch.queue_bind(self.queue_name, self.main_exchange_name, routing_key=self.queue_name)

        # The value defines the maximum number of unacknowledged deliveries that are permitted on a channel.
        # When the number reaches the configured count, RabbitMQ will stop delivering more messages on the
        # channel until at least one of the outstanding ones is acknowledged.
        ch.basic_qos(prefetch_count=self.batch_size)

        logger.info(f"Queue {self.queue_name} set up successfully with exchange {self.main_exchange_name} "
                    f"and DLX {self.dlx_exchange}.")

    def get_total_messages(self, channel: pika.adapters.blocking_connection.BlockingChannel) -> int:

        """Get the total number of messages in the queue.
        :param channel: The RabbitMQ channel
        :return: The number of messages in the queue, or 0 if the queue does not exist or an error occurs.
        :raises ChannelClosedByBroker: If the queue does not exist or is declared with different options.
        :raises AMQPError: If there is an error related to the AMQP protocol
        :raises Exception: For any other unexpected errors.
        """
        try:
            # Use passive=True to avoid creating a queue if it doesn't exist
            status = channel.queue_declare(queue=self.queue_name, durable=True, passive=True)
            return status.method.message_count
        # This exception will catch the issue when the queue does not exist or the queue
        #is declared with different arguments or some permission issue.
        except pika.exceptions.ChannelClosedByBroker as e:
            logger.warning(f"Queue '{self.queue_name}' does not exist: {e}")
            return 0
        # This exception will catch all the issue related to the AMQP protocol (Advanced Message Queuing Protocol)
        # Something went wrong at the protocol level, but pika cannot provide a
        # more specific exception
        except pika.exceptions.AMQPError as e:
            logger.error(f"Failed to get message count for queue '{self.queue_name}': {e}")
            return 0
        except Exception as e:
            logger.exception(
                f"Unexpected error while counting messages in queue '{self.queue_name}': {e}"
            )
            return 0