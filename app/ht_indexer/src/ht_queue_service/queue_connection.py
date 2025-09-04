import pika
from pika.exceptions import AMQPConnectionError, ProbableAuthenticationError
from ht_utils.ht_errors import HTError
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

    def __init__(self, user: str, password: str, host: str):
        # Define credentials (user/password) as environment variables
        # Declaring the credentials needed for connection, such as host, port, username, password, and exchange.

        self.credentials = pika.PlainCredentials(username=user, password=password)

        self.user = user
        self.password = password
        self.host = host
        self.queue_connection = self._connect()

    def _connect(self) -> pika.BlockingConnection:
        """ Establish a connection to the RabbitMQ server """
        try:
            return pika.BlockingConnection(
                pika.ConnectionParameters(host=self.host, credentials=self.credentials, heartbeat=0)
            )
        # pika.exceptions.AMQPConnectionError - Catch all the issue related to the
        # AMQP protocol (Advanced Message Queuing Protocol)
        # Something went wrong at the protocol level
        # pika.exceptions.ProbableAuthenticationError - Raised when the authentication fails
        except (
                ProbableAuthenticationError,
                AMQPConnectionError
        ) as e:
            raise HTError(
                f"Could not connect to RabbitMQ at {self.host}. Please check your connection settings."
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error while connecting to RabbitMQ: {e}")
            raise HTError(f"Could not connect to RabbitMQ at {self.host}.") from e


    def close(self) -> None:
        """ Close the connection to the RabbitMQ server """
        try:
            if self.queue_connection and not self.queue_connection.is_closed:
                self.queue_connection.close()
                logger.info("RabbitMQ connection closed.")
        except Exception as e:
            logger.warning(f"Error closing RabbitMQ connection: {e}")
        finally:
            # Set the connection to None to avoid using it after closing
            self.queue_connection = None
