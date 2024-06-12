import pika


class QueueConnection:

    def __init__(self, user: str, password: str, host: str, queue_name: str):
        # Define credentials (user/password) as environment variables
        # declaring the credentials needed for connection like host, port, username, password, exchange etc.

        try:
            self.credentials = pika.PlainCredentials(username=user, password=password)

            self.host = host
            self.queue_name = queue_name
            self.exchange = 'ht_channel'

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
        ht_channel.basic_qos(prefetch_count=1)

        return ht_channel

    def queue_reconnect(self):
        self.__init__(self.credentials.username, self.credentials.password, self.host, self.queue_name)

    def get_total_messages(self):
        # durable: Survive reboots of the broker
        # passive: Only check to see if the queue exists and raise `ChannelClosed` if it doesn't
        status = self.ht_channel.queue_declare(self.queue_name, durable=True, passive=True)
        return status.method.message_count
