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

class QueueConnection:

    def __init__(self, user: str, password: str, host: str, queue_name: str, batch_size: int = 1):
        # Define credentials (user/password) as environment variables
        # Declaring the credentials needed for connection, such as host, port, username, password, and exchange.

        self.credentials = pika.PlainCredentials(username=user, password=password)

        self.user = user
        self.password = password
        self.host = host
        self.queue_name = queue_name
        # TODO: make the exchange name configurable
        self.exchange = 'ht_channel'
        self.batch_size = batch_size
        self._connect()

    def _connect(self):
        self.queue_connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.host, credentials=self.credentials, heartbeat=0)
        )
        self.ht_channel = self.ht_queue_connection()

    def ht_queue_connection(self):

        """
        A Queue name is important when you want to share the queue between producers and consumers
        channel - a channel is a virtual connection inside a connection

        exchange - this can be assumed as a bridge name that needed to be declared so that queues can be accessed
        Direct – the exchange forwards the message to a queue based on a routing key

        The value defines the maximum number of unacknowledged deliveries that are permitted on a channel.
        When the number reaches the configured count, RabbitMQ will stop delivering more messages on the
        channel until at least one of the outstanding ones is acknowledged.
        """
        # Get a channel
        ht_channel = self.queue_connection.channel()

        # declare the exchange
        ht_channel.exchange_declare(self.exchange, durable=True, exchange_type="direct", auto_delete=False)

        ht_channel.basic_qos(prefetch_count=self.batch_size)

        return ht_channel

    def queue_reconnect(self):

        """ Reconnect to RabbitMQ server """

        logger.info(f"Reconnecting to RabbitMQ at {self.host}")
        try:
            if self.queue_connection and not self.queue_connection.is_closed:
                self.queue_connection.close()
        except Exception:
            pass
        self._connect()

    def close(self):
        """ Close the connection to RabbitMQ server """
        try:
            if self.queue_connection and not self.queue_connection.is_closed:
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
        # This exception will catch all the issue related to the AMQP protocol (Advanced Message Queuing Protocol)
        # Something went wrong at the protocol level, but pika cannot provide a
        # more specific exception
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
