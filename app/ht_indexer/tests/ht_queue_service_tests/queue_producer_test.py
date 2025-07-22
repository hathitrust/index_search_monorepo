import pytest
import json

from pika.exceptions import ChannelClosedByBroker, ChannelWrongStateError

from ht_queue_service.queue_consumer import QueueConsumer
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

message = {"ht_id": "12345678", "ht_title": "Hello World", "ht_author": "John Doe"}

@pytest.fixture()
def queue_name(test_name):
    """Fixture to provide a queue name."""
    dic_queue_test_names = {
        "test_queue_produce_one_message": "test_queue_produce_one_message",
        "test_queue_invalid": "test_queue_invalid",
        "test_queue_reconnect": "test_queue_reconnect"
    }
    return dic_queue_test_names[test_name]

class TestQueueProducer:
    """Test the QueueProducer class"""

    # TODO: This test does not make sense, because the queue is created in the QueueProducer class.
    # Add this test to the class QueueControllerTest when I implement it.
    def queue_does_not_exist(self, get_rabbit_mq_host_name):
        """Test that the queue does not exist before publishing messages."""
        queue_name = "test_queue_does_not_exist"

        # Create a producer instance to publish the message
        producer_instance = QueueProducer(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name=queue_name,
            batch_size=1
        )

        logger.info(f"Test will fail if the queue {queue_name} does not exist before publishing messages")

        try:
            producer_instance.channel.queue_purge(queue_name)
            pytest.fail("Should have raised an exception")
        except Exception as exc_info:
            assert isinstance(exc_info, (ChannelWrongStateError, ChannelClosedByBroker))
            assert "NOT_FOUND" in str(exc_info.args), \
                f"Expected 'NOT_FOUND' in exception message, got {exc_info.args}"

        producer_instance.queue_connection.close()


    def test_queue_produce_one_message(self, get_rabbit_mq_host_name):

        queue_name = "test_queue_produce_one_message"
        producer_instance = QueueProducer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            queue_name,
            batch_size=1
        )

        producer_instance.publish_messages(message)
        producer_instance.channel.close()

        # Consume the message to ensure it was published correctly
        consumer_instance = QueueConsumer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            queue_name,
            requeue_message=False,
            batch_size=1
        )

        list_message = []
        for method_frame, properties, body in consumer_instance.consume_message(inactivity_timeout=5):

            if method_frame:
                output_message = json.loads(body.decode('utf-8'))
                list_message.append(output_message)
                consumer_instance.positive_acknowledge(consumer_instance.channel, method_frame.delivery_tag)
                assert len(list_message) == 1
                break
            else:
                logger.warning(f"None method_frame in {consumer_instance.queue_name}... Stopping batch consumption.")
                break

    def test_publish_invalid_message_raises_type_error(self, get_rabbit_mq_host_name):

        """Test non-serializable data - Invalid message format"""

        producer_instance = QueueProducer("guest",
                                          "guest",
                                          get_rabbit_mq_host_name,
                                          "test_queue_invalid",
                                          batch_size=1
        )

        class NonSerializable:
            pass

        with pytest.raises(TypeError):
            producer_instance.publish_messages({"ht_id": "123", "payload": NonSerializable()})

        # Add close method to ensure the connection is closed after the test
        producer_instance.channel.close()
        producer_instance.queue_connection.close()

    def test_queue_reconnect(self, get_rabbit_mq_host_name):

        producer_instance = QueueProducer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            "test_queue_reconnect",
            batch_size=1
        )

        # Check if the connection is open
        assert producer_instance.queue_connection.is_open
        assert producer_instance.channel.is_open


        # Close the channel
        producer_instance.channel.close()

        assert producer_instance.channel.is_closed

        producer_instance.queue_reconnect()

        assert producer_instance.channel.is_open

        # Close channel and connection after the test
        producer_instance.channel.close()
        producer_instance.queue_connection.close()
