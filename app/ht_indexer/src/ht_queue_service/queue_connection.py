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

class QueueConnectionError(Exception):
    """Custom exception for queue connection issues."""
    pass

class QueueConnection:

    def __init__(self, user: str, password: str, host: str):
        # Define credentials (user/password) as environment variables
        # Declaring the credentials needed for connection, such as host, port, username, password, and exchange.

        self.credentials = pika.PlainCredentials(username=user, password=password)

        self.user = user
        self.password = password
        self.host = host
        self.queue_connection = self._connect()

    def _connect(self):
        """ Establish a connection to RabbitMQ server """
        try:
            return pika.BlockingConnection(
                pika.ConnectionParameters(host=self.host, credentials=self.credentials, heartbeat=0)
            )
        # pika.exceptions.AMQPConnectionError - Catch all the issue related to the AMQP protocol (Advanced Message Queuing Protocol)
        # Something went wrong at the protocol level
        # pika.exceptions.ProbableAuthenticationError - Raised when the authentication fails
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

    #self.ht_channel = self.ht_queue_connection()
    def close(self):
        """ Close the connection to RabbitMQ server """
        try:
            if self.queue_connection and not self.queue_connection.is_closed:
                self.queue_connection.close()
                logger.info("RabbitMQ connection closed.")
        except Exception as e:
            logger.warning(f"Error closing RabbitMQ connection: {e}")
        finally:
            # Set the connection to None to avoid using it after closing
            self.queue_connection = None

    #def queue_reconnect(self):
    #    # TODO: Check this function
    #    """ Reconnect to RabbitMQ server """

    #    logger.info(f"Reconnecting to RabbitMQ at {self.host}")
    #    try:
    #        if self.queue_connection and not self.queue_connection.is_closed:
    #            self.queue_connection.close()
    #    except Exception:
    #        pass
    #    self._connect()

    def is_ready(self) -> bool:
        # TODO: Check this function
        return self.queue_connection and self.ht_channel and not self.ht_channel.is_closed

    def get_total_messages(self, channel, queue_name) -> int:
        # TODO: Check this function
        try:
            # Ensure a channel is open
            if not self.is_ready():
                self.queue_reconnect()

            # Use passive=True to avoid creating a queue if it doesn't exist
            status = channel.queue_declare(
                queue=queue_name, durable=True, passive=True
            )
            return status.method.message_count
        # This exception will catch the issue when the queue does not exist or the queue
        #is declared with different arguments or some permission issue.
        except pika.exceptions.ChannelClosedByBroker as e:
            logger.warning(f"Queue '{queue_name}' does not exist: {e}")
            self.queue_reconnect()
            return 0
        # This exception will catch all the issue related to the AMQP protocol (Advanced Message Queuing Protocol)
        # Something went wrong at the protocol level, but pika cannot provide a
        # more specific exception
        except pika.exceptions.AMQPError as e:
            logger.error(f"Failed to get message count for queue '{queue_name}': {e}")
            self.queue_reconnect()
            return 0

        except Exception as e:
            logger.exception(
                f"Unexpected error while counting messages in queue '{queue_name}': {e}"
            )
            self.queue_reconnect()
            return 0
