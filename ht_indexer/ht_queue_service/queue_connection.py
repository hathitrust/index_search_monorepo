import pika

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
        # declaring the credentials needed for connection like host, port, username, password, exchange etc.

        try:
            self.credentials = pika.PlainCredentials(username=user, password=password)

            self.host = host
            self.queue_name = queue_name
            self.exchange = 'ht_channel'
            self.batch_size = batch_size

            # Open a connection to RabbitMQ
            self.queue_connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host,
                                                                                      credentials=self.credentials,
                                                                                      heartbeat=0))
            self.ht_channel = self.ht_queue_connection()
        except Exception as e:
            raise e

    def ht_queue_connection(self):
        # queue a name is important when you want to share the queue between producers and consumers

        # channel - a channel is a virtual connection inside a connection
        # get a channel
        ht_channel = self.queue_connection.channel()

        # exchange - this can be assumed as a bridge name which needed to be declared so that queues can be accessed
        # declare the exchange
        # Direct – the exchange forwards the message to a queue based on a routing key
        ht_channel.exchange_declare(self.exchange, durable=True, exchange_type="direct", auto_delete=False)

        ht_channel.queue_bind(self.queue_name, self.exchange, routing_key=self.queue_name)

        # The value defines the max number of unacknowledged deliveries that are permitted on a channel.
        # When the number reaches the configured count, RabbitMQ will stop delivering more messages on the
        # channel until at least one of the outstanding ones is acknowledged.
        ht_channel.basic_qos(prefetch_count=self.batch_size)

        return ht_channel

    def queue_reconnect(self):
        self.__init__(self.credentials.username, self.credentials.password, self.host, self.queue_name)

    def get_total_messages(self):
        # durable: Survive reboots of the broker
        # passive: Only check to see if the queue exists and raise `ChannelClosed` if it doesn't
        status = self.ht_channel.queue_declare(self.queue_name, durable=True, passive=True)
        return status.method.message_count
