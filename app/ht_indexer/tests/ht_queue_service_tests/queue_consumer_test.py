import json
import time

import pytest
from conftest import get_rabbitmq_host_name
from ht_queue_service.queue_connection import QueueConnection
from ht_queue_service.queue_consumer import positive_acknowledge
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)
rabbit_mq_host = get_rabbitmq_host_name()

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
    for method_frame, _properties, body in consumer_instance.consume_message(inactivity_timeout=3):

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
                    f" with error: {e}")

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

    @pytest.mark.parametrize("retriever_parameters", [{"user": "guest", "password": "guest", "host": rabbit_mq_host,
                                                       "queue_name": "test_producer_queue",
                                                       "requeue_message": False,
                                                       "batch_size": 1}])
    def test_queue_consume_message(self,retriever_parameters, one_message, producer_instance, consumer_instance):
        """ Test for consuming a message from the queue
        One message is published and consumed, then at the end of the test the queue is empty
        """

        # Clean up the queue
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)

        # Publish the message
        producer_instance.publish_messages(one_message)

        for _method_frame, _properties, body in consumer_instance.consume_message(inactivity_timeout=1):
            output_message = json.loads(body.decode('utf-8'))
            assert output_message == one_message
            break

        assert 0 == consumer_instance.conn.get_total_messages()
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)

    @pytest.mark.parametrize("retriever_parameters", [{"user": "guest", "password": "guest", "host": rabbit_mq_host,
                                                       "queue_name": "test_producer_queue",
                                                       "requeue_message": False,
                                                       "batch_size": 1}])
    def test_queue_consume_message_empty(self, retriever_parameters, consumer_instance):
        """ Test for consuming a message from an empty queue"""

        # Clean up the queue
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)

        assert 0 == consumer_instance.conn.get_total_messages()
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)

    @pytest.mark.parametrize("retriever_parameters",
                             [{"user": "guest", "password": "guest", "host": rabbit_mq_host,
                               "queue_name": "test_producer_queue",
                               "requeue_message": False,
                               "batch_size": 1}])
    def test_queue_requeue_message_requeue_false(self, retriever_parameters, populate_queue, consumer_instance):
        """ Test for re-queueing a message from the queue, an error is raised, and the message is routed
        to the dead letter queue and discarded from the main queue"""

        check_queue = QueueConnection("guest", "guest", rabbit_mq_host,
                                      "test_producer_queue_dead_letter_queue")

        # Requeue = False, the message is routed to the dead letter queue
        # consumer_instance could be 0 message and the dead letter queue could be 1 message
        assert 0 == consumer_instance.conn.get_total_messages()
        assert 1 == check_queue.get_total_messages()

        check_queue.ht_channel.queue_purge(check_queue.queue_name)

    @pytest.mark.parametrize("retriever_parameters",
                             [{"user": "guest", "password": "guest", "host": rabbit_mq_host,
                               "queue_name": "test_producer_queue",
                               "requeue_message": True,
                               "batch_size": 1}])
    def test_queue_requeue_message_requeue_true(self, retriever_parameters, populate_queue, consumer_instance):
        """ Test for re-queueing a message from the queue, an error is raised, and instead of routing the message
        to the dead letter queue, it is requeue to the main queue"""

        check_queue = QueueConnection("guest", "guest", rabbit_mq_host,
                                      "test_producer_queue_dead_letter_queue")

        assert consumer_instance.conn.get_total_messages() > 0
        assert 0 == check_queue.get_total_messages()

        check_queue.ht_channel.queue_purge(check_queue.queue_name)
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)
