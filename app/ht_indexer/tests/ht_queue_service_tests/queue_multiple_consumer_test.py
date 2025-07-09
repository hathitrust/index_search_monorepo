import pytest
from ht_queue_service.queue_connection import QueueConnection
from ht_queue_service.queue_multiple_consumer import QueueMultipleConsumer, positive_acknowledge
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

class HTMultipleConsumerServiceConcrete(QueueMultipleConsumer):

    def __init__(self, user: str, password: str, host: str, queue_name: str, requeue_message: bool = False,
                 batch_size: int = 1, shutdown_on_empty_queue: bool = True):
        super().__init__(user, password, host, queue_name, requeue_message, batch_size)
        self.consume_one_message = None
        self.shutdown_on_empty_queue = shutdown_on_empty_queue

    def process_batch(self, batch: list, delivery_tags: list):

        try:
            list_id = [doc.get("ht_id") for doc in batch]
            received_messages = batch.copy()
            if "5" in list_id:
                try:
                    print(1 / 0)
                except Exception as e:
                    logger.error(f"Error in indexing document: {e}")
                    raise e

            # Acknowledge the message if the message is processed successfully
            for tag in delivery_tags:
                positive_acknowledge(self.conn.ht_channel, tag)
            self.consume_one_message = received_messages

            batch.clear()
            delivery_tags.clear()
        except Exception as e:
                logger.info(
                    f"Message failed with error: {e}")
                failed_messages_tags = delivery_tags.copy()

                # Reject the message
                for delivery_tag in failed_messages_tags:
                    self.reject_message(self.conn.ht_channel, delivery_tag)

        # Stop consuming if the flag is set
        if self.shutdown_on_empty_queue and self.conn.get_total_messages() == 0:
            logger.info("Stopping consumer...")
            self.conn.ht_channel.stop_consuming()
            return False

@pytest.fixture
def one_message():
    """
    This function is used to create a message
    """
    message = {"ht_id": "1234", "ht_title": "Hello World", "ht_author": "John Doe"}
    return message


@pytest.fixture
def list_messages():
    """
    This function is used to create a list of messages
    """

    messages = []
    for i in range(10):
        messages.append({"ht_id": f"{i}", "ht_title": f"Hello World {i}", "ht_author": f"John Doe {i}"})
    return messages

@pytest.fixture
def multiple_consumer_instance(get_rabbit_mq_host_name):
    return HTMultipleConsumerServiceConcrete(user="guest", password="guest", host=get_rabbit_mq_host_name,
                                                 queue_name="test_producer_queue", requeue_message=False, batch_size=1)

@pytest.fixture
def multiple_consumer_instance_requeue_true_size_n(get_rabbit_mq_host_name):
    return HTMultipleConsumerServiceConcrete(user="guest", password="guest", host=get_rabbit_mq_host_name,
                                                 queue_name="test_producer_queue", requeue_message=True, batch_size=10)

@pytest.fixture
def multiple_consumer_instance_requeue_false_size_n(get_rabbit_mq_host_name):
    return HTMultipleConsumerServiceConcrete(user="guest", password="guest", host=get_rabbit_mq_host_name,
                                                 queue_name="test_producer_queue", requeue_message=False, batch_size=10)

@pytest.fixture
def populate_queue(list_messages, producer_instance, multiple_consumer_instance_requeue_false_size_n, retriever_parameters):
    """ Test for re-queueing a message from the queue, an error is raised, and the message is routed
            to the dead letter queue and discarded from the main queue"""

    # Clean up the queue
    multiple_consumer_instance_requeue_false_size_n.conn.ht_channel.queue_purge(multiple_consumer_instance_requeue_false_size_n.queue_name)

    for message in list_messages:
        # Publish the message
        producer_instance.publish_messages(message)

    multiple_consumer_instance_requeue_false_size_n.start_consuming()

@pytest.fixture
def populate_queue_requeue_true(list_messages, producer_instance, multiple_consumer_instance_requeue_true_size_n, retriever_parameters):
    """ Test for re-queueing a message from the queue, an error is raised, and the message is routed
            to the dead letter queue and discarded from the main queue"""

    # Clean up the queue
    multiple_consumer_instance_requeue_true_size_n.conn.ht_channel.queue_purge(multiple_consumer_instance_requeue_true_size_n.queue_name)

    for message in list_messages:
        # Publish the message
        producer_instance.publish_messages(message)

    multiple_consumer_instance_requeue_true_size_n.start_consuming()

class TestHTMultipleConsumerService:

    @pytest.mark.parametrize("retriever_parameters", [{"user": "guest", "password": "guest",
                                                       "host": "get_rabbit_mq_host_name",
                                                       "queue_name": "test_producer_queue",
                                                       "batch_size": 1}],
                             indirect=["retriever_parameters"])
    def test_queue_consume_message(self, retriever_parameters, one_message, producer_instance, multiple_consumer_instance):
        """ Test for consuming a message from the queue
        One message is published and consumed, then at the end of the test the queue is empty
        """

        # Clean up the queue
        multiple_consumer_instance.conn.ht_channel.queue_purge(multiple_consumer_instance.queue_name)

        # Publish the message
        producer_instance.publish_messages(one_message)

        multiple_consumer_instance.start_consuming()

        output_message = multiple_consumer_instance.consume_one_message
        assert output_message[0] == one_message

        # Queue is empty
        assert 0 == multiple_consumer_instance.conn.get_total_messages()

        multiple_consumer_instance.conn.ht_channel.queue_purge(multiple_consumer_instance.queue_name)

    def test_queue_consume_message_empty(self, multiple_consumer_instance):
        """ Test for consuming a message from an empty queue"""

        # Clean up the queue
        multiple_consumer_instance.conn.ht_channel.queue_purge(multiple_consumer_instance.queue_name)

        assert 0 == multiple_consumer_instance.conn.get_total_messages()
        multiple_consumer_instance.conn.ht_channel.queue_purge(multiple_consumer_instance.queue_name)

    @pytest.mark.parametrize("retriever_parameters",
                             [{"user": "guest", "password": "guest", "host": "get_rabbit_mq_host_name",
                               "queue_name": "test_producer_queue",
                               "requeue_message": False, "batch_size": 10}],
                             indirect=["retriever_parameters"])
    def test_queue_requeue_message_requeue_false(self, retriever_parameters, populate_queue,
                                                 multiple_consumer_instance_requeue_false_size_n):
        """ Test for re-queueing a message from the queue, an error is raised, and the message is routed
        to the dead letter queue and discarded from the main queue"""

        check_queue = QueueConnection("guest", "guest", retriever_parameters["host"],
                                      "test_producer_queue_dead_letter_queue")

        # Requeue = False, the message is routed to the dead letter queue
        # consumer_instance could be 0 message and the dead letter queue could be 1 message
        assert 0 == multiple_consumer_instance_requeue_false_size_n.conn.get_total_messages()
        # All the messages are back into the dead letter queue
        assert 10 == check_queue.get_total_messages()

        multiple_consumer_instance_requeue_false_size_n.conn.ht_channel.queue_purge(multiple_consumer_instance_requeue_false_size_n.queue_name)
        check_queue.ht_channel.queue_purge(check_queue.queue_name)

    @pytest.mark.parametrize("retriever_parameters",
                             [{"user": "guest", "password": "guest", "host": "get_rabbit_mq_host_name",
                               "queue_name": "test_producer_queue",
                               "requeue_message": True, "batch_size": 1}],
                             indirect=["retriever_parameters"])
    def test_queue_requeue_message_requeue_true(self, retriever_parameters, populate_queue_requeue_true,
                                                multiple_consumer_instance_requeue_true_size_n,
                                                get_rabbit_mq_host_name):
        """ Test for re-queueing a message from the queue, an error is raised, and instead of routing the message
        to the dead letter queue, it is requeue to the main queue """

        check_queue = QueueConnection("guest", "guest", get_rabbit_mq_host_name,
                                      "test_producer_queue_dead_letter_queue", batch_size=1)

        assert multiple_consumer_instance_requeue_true_size_n.conn.get_total_messages() > 0
        assert 0 == check_queue.get_total_messages()

        check_queue.ht_channel.queue_purge(check_queue.queue_name)
        multiple_consumer_instance_requeue_true_size_n.conn.ht_channel.queue_purge(multiple_consumer_instance_requeue_true_size_n.queue_name)



