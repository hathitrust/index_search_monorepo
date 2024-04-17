import pika


def ht_queue_connection(queue_connection: pika.BlockingConnection, ht_exchange: str, queue_name: str):
    # queue a name is important when you want to share the queue between producers and consumers

    # channel - a channel is a virtual connection inside a connection
    # get channel
    ht_channel = queue_connection.channel()

    # exchange - this can be assumed as a bridge name which needed to be declared so that queues can be accessed
    # declare the exchange
    # Direct – the exchange forwards the message to a queue based on a routing key
    ht_channel.exchange_declare(ht_exchange, durable=True, exchange_type="direct")

    # Check if the queue exist
    # Declare a queue
    ht_channel.queue_declare(queue=queue_name, durable=True, exclusive=False, auto_delete=False)

    # The relationship between exchange and a queue is called a binding.
    # Link the exchange to the queue to send messages.
    ht_channel.queue_bind(exchange=ht_exchange, queue=queue_name, routing_key=queue_name)

    ht_channel.basic_qos(prefetch_count=1)

    ht_channel.confirm_delivery()
    return ht_channel


class QueueConnection:

    def __init__(self, user: str, password: str, host: str, queue_name: str):
        # Define credentials (user/password) as environment variables
        # declaring the credentials needed for connection like host, port, username, password, exchange etc
        self.credentials = pika.PlainCredentials(username=user, password=password)

        self.host = host
        self.queue_name = queue_name
        self.exchange = 'ht_channel'

        # Open a connection to RabbitMQ
        self.queue_connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host,
                                                                                  credentials=self.credentials,
                                                                                  heartbeat=5))
        self.ht_channel = ht_queue_connection(self.queue_connection, self.exchange, self.queue_name)
