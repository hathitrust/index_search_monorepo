import pika
import pika.exceptions

from ht_queue_service.queue_connection import QueueConnection
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

def declare_channel(channel,
                queue_name: str,
                exchange_name: str,
                exchange_type: str,
                routing_key: str,
                durable: bool,
                auto_delete: bool) -> pika.adapters.blocking_connection.BlockingChannel:


    """
    Create a channel to the RabbitMQ server and declare the exchange and queue.

    A Queue name is important when you want to share the queue between producers and consumers
    channel - a channel is a virtual connection inside a connection

    exchange - this can be assumed as a bridge name that needed to be declared so that queues can be accessed
    Direct – the exchange forwards the message to a queue based on a routing key

    The value defines the maximum number of unacknowledged deliveries that are permitted on a channel.
    When the number reaches the configured count, RabbitMQ will stop delivering more messages on the
    channel until at least one of the outstanding ones is acknowledged.
    """
    try:
        # Get a channel
        # ht_channel = queue_connection.channel()

        # declare the main exchange
        channel.exchange_declare(exchange_name,
                                    exchange_type=exchange_type,
                                    durable=durable,
                                    auto_delete=auto_delete)

        # Declare the dead-letter exchange
        #ht_channel.exchange_declare(self.dlx_exchange, exchange_type=self.exchange_type, durable=True)

        # Declare the queue with dead-letter configuration
        #self._declare_queue_dead_letter_queue(ht_channel)
        # Bind the dead letter exchange to the dead letter queue
        # The queue_bind method binds a queue to an exchange. The queue will now receive messages from the exchange,
        # Otherwise, no messages will be routed to the queue.
        #ht_channel.queue_bind(
        #    f"{self.queue_name}_dead_letter_queue", self.dlx_exchange, f"dlx_key_{self.queue_name}"
        #)

    # pika.exceptions.ChannelClosed - Raised when the broker closes the channel
    except pika.exceptions.ChannelClosedByBroker as e:
        raise QueueConnectionError(f"Broker closed the channel: {e}")
    except pika.exceptions.AMQPError as e:
        raise QueueConnectionError(f"AMQP error while setting up queue: {e}")
    except Exception as e:
        raise QueueConnectionError(f"Unexpected error during queue setup: {e}")
    return ht_channel


class QueueSetup():
    """
    We use a dead-letter-exchange to handle messages that are not processed successfully.
    The dead-letter-exchange is an exchange to which messages will be re-routed if they are rejected by the queue.
    See a detail explanation of dead letter exchanges here: https://www.rabbitmq.com/docs/dlx#overview
    A message is dead-lettered if it is negatively acknowledged and requeued, or if it times out.
    """

    def __init__(self, queue_conn: QueueConnection, queue_name: str, batch_size: int = 1):
        # Call the parent class constructor that initializes the connection to the queue
        #super().__init__(user, password, host, queue_name, batch_size)
        self.queue_connection = queue_conn.queue_connection
        self.queue_name = queue_name
        self.batch_size = batch_size
        #self.main_exchange = queue_name  # Use the queue name as the main exchange
        # Declare the main exchange
        self.main_channel = declare_channel(queue_conn.main_channel,
                                            self.queue_name,
                                            self.main_exchange,
                                            self.exchange_type,
                                            self.queue_name,
                                            self.durable,
                                            self.auto_delete)

        # Declare the dead letter exchange

        self.dlx_exchange = queue_conn.queue_connection.exchange_declare()
        self.dlx_exchange = queue_connection.channel()




    def _create_channel(self):
        # queue a name is important when you want to share the queue between producers and consumers
        # channel - a channel is a virtual connection inside a connection
        # get a channel
        ht_channel = self.queue_connection.channel()

        # exchange - this can be assumed as a bridge name which needs to be declared so that queues can be accessed
        # declare the exchange
        # Direct – the exchange forwards the message to a queue based on a routing key
        ht_channel.exchange_declare(self.main_exchange, durable=True, exchange_type="direct", auto_delete=False)

        # Declare the dead letter exchange
        ht_channel.exchange_declare("dlx", durable=True, exchange_type="direct")

        # Declare the dead letter exchange to the original queue
        _declare_queue_dead_letter_queue(ht_channel, self.queue_name)

        # Declare the dead letter queue
        ht_channel.queue_declare(f"{self.queue_name}_dead_letter_queue")

        # Bind the dead letter exchange to the dead letter queue
        # The queue_bind method binds a queue to an exchange. The queue will now receive messages from the exchange,
        # Otherwise, no messages will be routed to the queue.
        ht_channel.queue_bind(f"{self.queue_name}_dead_letter_queue", "dlx", f"dlx_key_{self.queue_name}")

        # The relationship between exchange and a queue is called a binding.
        # Link the exchange to the queue to send messages.
        ht_channel.queue_bind(self.queue_name, self.main_exchange, routing_key=self.queue_name)

        # The value defines the maximum number of unacknowledged deliveries that are permitted on a channel.
        # When the number reaches the configured count, RabbitMQ will stop delivering more messages on the
        # channel until at least one of the outstanding ones is acknowledged.
        ht_channel.basic_qos(prefetch_count=self.batch_size)

        return ht_channel
