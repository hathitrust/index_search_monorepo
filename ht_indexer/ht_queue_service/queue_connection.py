import pika


def ht_declare_dead_letter_queue(ht_channel: pika.connection, queue_name: str):
    """
    Declare the dead letter queue
    """

    # Check if the queue exist
    # Declare a queue
    # durable=True - the queue will survive a broker restart
    # exclusive=False - the queue can be accessed in other channels
    # auto_delete=False - the queue won't be deleted once the consumer is disconnected
    # arguments - the dead-letter-exchange and dead-letter-routing-key are used to define the dead letter exchange
    # and the routing key to use when a message is dead-lettered.
    ht_channel.queue_declare(queue=queue_name, durable=True, exclusive=False, auto_delete=False,
                             arguments={'x-dead-letter-exchange': 'dlx',
                                        "x-dead-letter-routing-key": f"dlx_key_{queue_name}"}
                             )


def ht_queue_connection(queue_connection: pika.BlockingConnection, ht_exchange: str, queue_name: str,
                        dead_letter_queue: bool = True):
    # queue a name is important when you want to share the queue between producers and consumers

    # channel - a channel is a virtual connection inside a connection
    # get a channel
    ht_channel = queue_connection.channel()

    # exchange - this can be assumed as a bridge name which needed to be declared so that queues can be accessed
    # declare the exchange
    # Direct – the exchange forwards the message to a queue based on a routing key
    ht_channel.exchange_declare(ht_exchange, durable=True, exchange_type="direct", auto_delete=False)

    # We use a dead-letter-exchange to handle messages that are not processed successfully.
    # The dead-letter-exchange is an exchange to which messages will be re-routed if they are rejected by the queue.
    # See a detail explanation of dead letter exchanges here: https://www.rabbitmq.com/docs/dlx#overview
    # A message is dead-lettered if it is negatively acknowledged and requeued, or if it times out.

    if dead_letter_queue:
        # Declare the dead letter exchange
        ht_channel.exchange_declare("dlx", durable=True, exchange_type="direct")

        # Declare the dead letter exchange to the original queue
        ht_declare_dead_letter_queue(ht_channel, queue_name)

        # Declare the dead letter queue
        ht_channel.queue_declare(f"{queue_name}_dead_letter_queue")

        # Bind the dead letter exchange to the dead letter queue
        # The queue_bind method binds a queue to an exchange. The queue will now receive messages from the exchange,
        # otherwise no messages will be routed to the queue.
        ht_channel.queue_bind(f"{queue_name}_dead_letter_queue", "dlx", f"dlx_key_{queue_name}")

    # The relationship between exchange and a queue is called a binding.
    # Link the exchange to the queue to send messages.
    ht_channel.queue_bind(exchange=ht_exchange, queue=queue_name, routing_key=queue_name)

    # The value defines the max number of unacknowledged deliveries that are permitted on a channel.
    # When the number reaches the configured count, RabbitMQ will stop delivering more messages on the
    # channel until at least one of the outstanding ones is acknowledged.
    ht_channel.basic_qos(prefetch_count=1)

    return ht_channel


class QueueConnection:

    def __init__(self, user: str, password: str, host: str, queue_name: str, dead_letter_queue: bool = True):
        # Define credentials (user/password) as environment variables
        # declaring the credentials needed for connection like host, port, username, password, exchange etc.

        try:
            self.credentials = pika.PlainCredentials(username=user, password=password)

            self.host = host
            self.queue_name = queue_name
            self.exchange = 'ht_channel'
            self.dead_letter_queue = dead_letter_queue

            # Open a connection to RabbitMQ
            self.queue_connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host,
                                                                                      credentials=self.credentials,
                                                                                      heartbeat=0))
            self.ht_channel = ht_queue_connection(self.queue_connection, self.exchange, self.queue_name,
                                                  dead_letter_queue=self.dead_letter_queue)
        except Exception as e:
            raise e
        
    def queue_reconnect(self):
        self.__init__(self.credentials.username, self.credentials.password, self.host, self.queue_name,
                      self.dead_letter_queue)
        if self.dead_letter_queue:
            ht_declare_dead_letter_queue(self.ht_channel, self.queue_name)

    def get_total_messages(self):
        # durable: Survive reboots of the broker
        # passive: Only check to see if the queue exists and raise `ChannelClosed` if it doesn't
        status = self.ht_channel.queue_declare(queue=self.queue_name, durable=True, passive=True)
        return status.method.message_count
