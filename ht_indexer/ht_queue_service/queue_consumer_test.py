import json
import pytest
import time

from ht_queue_service.queue_consumer import QueueConsumer, positive_acknowledge

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


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
    This function is used to create a message
    """

    messages = []
    for i in range(10):
        messages.append({"ht_id": f"{i}", "ht_title": f"Hello World {i}", "ht_author": f"John Doe {i}"})
    return messages


@pytest.fixture
def populate_queue(list_messages, producer_instance, consumer_instance, retriever_parameters):
    """ Test for re-queueing a message from the queue, an error is raised, and the message is routed
            to the dead letter queue and discarded from the main queue"""

    # Clean up the queue
    consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)

    for message in list_messages:
        # Publish the message
        producer_instance.publish_messages(message)

    start_time = time.time()
    for method_frame, properties, body in consumer_instance.consume_message(inactivity_timeout=3):

        if method_frame:
            try:
                # Process the message
                output_message = json.loads(body.decode('utf-8'))

                # Use the message to raise an exception
                if output_message.get("ht_id") == "5":
                    # This will raise an exception
                    logger.info(f"Message {output_message.get('ht_id')} processed successfully {1 / 0}")
                # Acknowledge the message if the message is processed successfully
                positive_acknowledge(consumer_instance.conn.ht_channel, method_frame.delivery_tag)
            except Exception as e:
                logger.info(
                    f"Message {method_frame.delivery_tag} re-queued to {consumer_instance.queue_name}"
                    f"with error: {e}")

                # Reject the message
                consumer_instance.reject_message(consumer_instance.conn.ht_channel, method_frame.delivery_tag)
                current_time = time.time()

                # This check was added to avoid the test to run indefinitely because the queue is not empty and
                # it is stuck
                if current_time - start_time > 60:
                    logger.info("The test is taking too long: Test ended")
                    break
                time.sleep(1)

        else:
            logger.info("Empty queue: Test ended")
            break


class TestHTConsumerService:

    @pytest.mark.parametrize("retriever_parameters", [{"user": "guest", "password": "guest", "host": "rabbitmq",
                                                       "queue_name": "test_producer_queue", "dead_letter_queue": True,
                                                       "requeue_message": False}])
    def test_queue_consume_message(self, one_message, producer_instance, consumer_instance):
        """ Test for consuming a message from the queue
        One message is published and consumed, then at the end of the test the queue is empty
        """

        # Clean up the queue
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)

        # Publish the message
        producer_instance.publish_messages(one_message)

        for method_frame, properties, body in consumer_instance.consume_message(inactivity_timeout=1):
            output_message = json.loads(body.decode('utf-8'))
            assert output_message == one_message
            break

        assert 0 == consumer_instance.conn.get_total_messages()

    @pytest.mark.parametrize("retriever_parameters", [{"user": "guest", "password": "guest", "host": "rabbitmq",
                                                       "queue_name": "test_producer_queue", "dead_letter_queue": True,
                                                       "requeue_message": False}])
    def test_queue_consume_message_empty(self, consumer_instance):
        """ Test for consuming a message from an empty queue"""

        # Clean up the queue
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)

        assert 0 == consumer_instance.conn.get_total_messages()

    @pytest.mark.parametrize("retriever_parameters",
                             [{"user": "guest", "password": "guest", "host": "rabbitmq",
                               "queue_name": "test_producer_queue", "dead_letter_queue": True,
                               "requeue_message": False}])
    def test_queue_requeue_message_requeue_false(self, populate_queue, consumer_instance):
        """ Test for re-queueing a message from the queue, an error is raised, and the message is routed
        to the dead letter queue and discarded from the main queue"""

        check_consumer = QueueConsumer("guest", "guest", "rabbitmq",
                                       "test_producer_queue_dead_letter_queue", dead_letter_queue=False,
                                       requeue_message=False)

        assert 0 == consumer_instance.conn.get_total_messages()
        assert 1 == check_consumer.conn.get_total_messages()

        check_consumer.conn.ht_channel.queue_purge(check_consumer.queue_name)

    @pytest.mark.parametrize("retriever_parameters",
                             [{"user": "guest", "password": "guest", "host": "rabbitmq",
                               "queue_name": "test_producer_queue", "dead_letter_queue": True,
                               "requeue_message": True}])
    def test_queue_requeue_message_requeue_true(self, populate_queue, consumer_instance):
        """ Test for re-queueing a message from the queue, an error is raised, and instead of routing the message
        to the dead letter queue, it is requeue to the main queue"""

        check_consumer = QueueConsumer("guest", "guest", "rabbitmq",
                                       "test_producer_queue_dead_letter_queue", dead_letter_queue=False,
                                       requeue_message=True)

        assert consumer_instance.conn.get_total_messages() > 0
        assert 0 == check_consumer.conn.get_total_messages()

        check_consumer.conn.ht_channel.queue_purge(check_consumer.queue_name)
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)
