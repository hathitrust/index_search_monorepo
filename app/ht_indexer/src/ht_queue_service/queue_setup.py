from ht_queue_service.queue_connection import QueueConnection

"""
    We use a dead-letter-exchange to handle messages that are not processed successfully.
    The dead-letter-exchange is an exchange to which messages will be re-routed if they are rejected by the queue.
    See a detail explanation of dead letter exchanges here: https://www.rabbitmq.com/docs/dlx#overview
    A message is dead-lettered if it is negatively acknowledged and requeued, or if it times out.
    """

def set_up_queue(channel, queue_name, exchange_name, dlx_exchange, exchange_type, durable, auto_delete,
                 queue_arguments, batch_size) -> None:
    # durable=True - the queue will survive a broker restart
    # exclusive=False - the queue can be accessed in other channels
    # auto_delete=False - the queue won't be deleted once the consumer is disconnected
    # arguments - the dead-letter-exchange and dead-letter-routing-key are used to define the dead letter exchange
    # and the routing key to use when a message is dead-lettered.

    # queue a name is important when you want to share the queue between producers and consumers
    # channel - a channel is a virtual connection inside a connection
    # get a channel

    # Declare the main exchange
    channel.exchange_declare(exchange_name,
                             exchange_type=exchange_type,
                             durable=durable,
                             auto_delete=auto_delete)

    # Declare the dead letter exchange
    channel.exchange_declare(dlx_exchange,
                             exchange_type=exchange_type,
                             durable=durable,
                             auto_delete=auto_delete)

    # Declare the main queue
    channel.queue_declare(queue=queue_name,
                          durable=durable,
                          exclusive=False,
                          auto_delete=auto_delete,
                          arguments=queue_arguments)

    # Declare the dead letter queue
    channel.queue_declare(f"{queue_name}_dlq")

    # Bind the dead letter exchange to the dead letter queue
    # The queue_bind method binds a queue to an exchange. The queue will now receive messages from the exchange,
    # Otherwise, no messages will be routed to the queue.
    channel.queue_bind(f"{queue_name}_dlq", dlx_exchange, f"dlx_key_{queue_name}")

    # The relationship between exchange and a queue is called a binding.
    # Link the exchange to the queue to send messages.
    channel.queue_bind(queue_name, exchange_name, routing_key=queue_name)

    # The value defines the maximum number of unacknowledged deliveries that are permitted on a channel.
    # When the number reaches the configured count, RabbitMQ will stop delivering more messages on the
    # channel until at least one of the outstanding ones is acknowledged.
    channel.basic_qos(prefetch_count=batch_size)
