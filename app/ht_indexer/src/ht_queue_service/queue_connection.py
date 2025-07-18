
import pika
import pika.exceptions
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

# Calculate the maximum number of messages in the queue

# The average size of a document_generator message is 1.8 MB
# The average size of a document_retriever message is 0.16 MB

# The total disk space of the RabbitMQ server is 50 GB.
# 1 GB = 1024 MB, so 50 GB = 50 * 1024 MB = 51,200 MB.

# Let's calculate using 90% of the total disk space 51,200 MB * 0.90 = 46,080 MB
# The maximum number of document_generator messages in the queue is 46,080 MB / 1.8 MB = 25,600 messages
# The maximum number of document_retriever messages in the queue is 46,080 MB / 0.16 MB = 288,000 messages

# To set the maximum number of messages in the retriever queue, I'll set it to 500,000 messages
MAX_DOCUMENT_IN_QUEUE = 200000 # 200000 is the maximum number of messages in the retriever queue

def create_channel(queue_connection: pika.BlockingConnection,
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
        ht_channel = queue_connection.channel()

        # declare the main exchange
        ht_channel.exchange_declare(exchange_name,
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

class QueueConnectionError(Exception):
    """Custom exception for queue connection issues."""
    pass

class QueueConnection:
    """
    Represents a connection to a RabbitMQ queue.

    This class manages the connection, channel, and queue interactions with a specified RabbitMQ broker.
    It facilitates operations such as message retrieval, queue inspection, and reconnection in case of
    communication failure.

    Attributes:
        user (str): Username used for connecting to RabbitMQ.
        password (str): Password for the RabbitMQ connection.
        host (str): Host address of the RabbitMQ server.
        queue_name (str): Name of the queue to interact with.
        exchange (str): Name of the RabbitMQ exchange to declare. Default is 'ht_channel'.
        batch_size (int): Prefetch count to define the maximum number of unacknowledged messages on a channel.
    """
    def __init__(self, user: str, password: str, host: str, queue_name: str, batch_size: int = 1,
                 exchange_name: str = 'ht_channel',
                 exchange_type: str = 'direct',
                 durable: bool = True,
                 auto_delete: bool = False):
        # Define credentials (user/password) as environment variables
        # Declaring the credentials needed for connection, such as host, port, username, password, and exchange.

        self.credentials = pika.PlainCredentials(username=user, password=password)
        # TODO add exponential backoff in queue_reconnect()
        self.user = user
        self.password = password
        self.host = host
        self.queue_name = queue_name
        self.exchange = exchange_name
        self.dlx_exchange = "dlx"  # Dead-letter exchange
        self.batch_size = batch_size
        self.exchange_type = exchange_type
        self.durable = durable  # Ensures the exchange and queue survive broker restarts
        self.auto_delete = auto_delete
        self._connect()

    def _connect(self):

        try:
            self.queue_connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=self.host, credentials=self.credentials, heartbeat=0)
            )

            # Create the channel for the main queue.
            self.ht_channel = create_channel(self.queue_connection,
                                             self.queue_name,
                                             self.exchange,
                                             self.exchange_type,
                                             self.queue_name,
                                             self.durable,
                                             self.auto_delete)

            # Create a channel for the dead-letter exchange
            self.dlx_channel = create_channel(self.queue_connection,
                                              f"{self.queue_name}_dead_letter_queue",
                                              self.dlx_exchange,
                                              self.exchange_type,
                                              f"dlx_key_{self.queue_name}",
                                              self.durable,
                                              self.auto_delete
                                              )

            self.ht_channel.basic_qos(prefetch_count=self.batch_size)

            logger.info(f"Queue {self.queue_name} and DLQ setup completed.")
            self._declare_queue_dead_letter_queue()

            # Bind the main queue to the exchange
            self.ht_channel.queue_bind(self.queue_name, self.exchange, routing_key=self.queue_name)
            self.dlx_channel.queue_bind(f"{self.queue_name}_dead_letter_queue", self.dlx_exchange,
                                         routing_key=f"dlx_key_{self.queue_name}")


        # pika.exceptions.AMQPConnectionError - Catch all the issue related to the AMQP protocol (Advanced Message Queuing Protocol)
        # Something went wrong at the protocol level
        # pika.exceptions.ProbableAuthenticationError - Raised when the authentication fails
        # socket.gaierror - Raised when the host name could not be resolved
        # socket.timeout - Raised when the connection times out
        except (
            pika.exceptions.ProbableAuthenticationError,
            pika.exceptions.AMQPConnectionError
        ) as e:
            raise QueueConnectionError(
                f"Could not connect to RabbitMQ at {self.host}. Please check your connection settings."
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error while connecting to RabbitMQ: {e}")
            raise QueueConnectionError(f"Could not connect to RabbitMQ at {self.host}.") from e

    def _declare_queue_dead_letter_queue(self):
        """
        Declare the dead letter queue
        """

        # durable=True - the queue will survive a broker restart
        # exclusive=False - the queue can be accessed in other channels
        # auto_delete=False - the queue won't be deleted once the consumer is disconnected
        # arguments - the dead-letter-exchange and dead-letter-routing-key are used to define the dead letter exchange
        # and the routing key to use when a message is dead-lettered.

        # Declare the dead letter queue
        self.dlx_channel.queue_declare(f"{self.queue_name}_dead_letter_queue", durable=True)

        # Declare the main queue with dead-letter configuration
        self.ht_channel.queue_declare(
            queue=self.queue_name,
            durable=True,
            exclusive=False,
            auto_delete=False,
            arguments={
                "x-dead-letter-exchange": self.dlx_exchange, #"dlx",
                "x-dead-letter-routing-key": f"dlx_key_{self.queue_name}",
            },
        )

    def queue_reconnect(self):

        """ Reconnect to RabbitMQ server """

        logger.info(f"Reconnecting to RabbitMQ at {self.host}")
        try:
            if self.queue_connection and not self.queue_connection.is_closed:
                self.queue_connection.close()
        except Exception:
            logger.error(f"RabbitMQ connection error: {self.queue_connection}")
            pass
        self._connect()

    def close(self):
        """ Close the connection to RabbitMQ server """
        try:
            if self.queue_connection and not self.queue_connection.is_closed:
                logger.info(f"Closing RabbitMQ connection at {self.host}")
                self.queue_connection.close()
        except Exception as e:
            logger.warning(f"Error closing RabbitMQ connection: {e}")

    def is_ready(self) -> bool:
        return self.queue_connection and self.ht_channel and not self.ht_channel.is_closed

    def get_total_messages(self) -> int:
        try:
            # Ensure a channel is open
            if not self.is_ready():
                self.queue_reconnect()

            # Use passive=True to avoid creating a queue if it doesn't exist
            status = self.ht_channel.queue_declare(
                queue=self.queue_name, durable=True, passive=True
            )
            return status.method.message_count
        # This exception will catch the issue when the queue does not exist or the queue
        #is declared with different arguments or some permission issue.
        except pika.exceptions.ChannelClosedByBroker as e:
            logger.warning(f"Queue '{self.queue_name}' does not exist: {e}")
            self.queue_reconnect()
            return 0
        except pika.exceptions.AMQPError as e:
            logger.error(f"Failed to get message count for queue '{self.queue_name}': {e}")
            self.queue_reconnect()
            return 0
        except Exception as e:
            logger.exception(
                f"Unexpected error while counting messages in queue '{self.queue_name}': {e}"
            )
            self.queue_reconnect()
            return 0
