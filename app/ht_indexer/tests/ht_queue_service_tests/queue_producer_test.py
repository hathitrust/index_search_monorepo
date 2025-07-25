import pytest
import json

from ht_queue_service.channel_factory import ChannelFactory
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

    def test_queue_produce_one_message(self, get_rabbit_mq_host_name):

        queue_name = "test_queue_produce_one_message"
        producer_instance = QueueProducer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            queue_name,
            batch_size=1,
            exchange_name="ht_exchange"
        )

        # Create the channel
        channel_factory = ChannelFactory(producer_instance)
        channel = channel_factory.get_channel()

        # TODO: Create a fixture to clean up the queue before each test
        # producer_instance.ht_channel.queue_purge(producer_instance.queue_name)

        producer_instance.publish_messages(message, channel)
        #assert producer_instance.get_total_messages(channel, queue_name) == 1
        channel_factory.close_channel()

        # Consume the message to ensure it was published correctly
        consumer_instance = QueueConsumer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            queue_name,
            requeue_message=False,
            batch_size=1,
            exchange_name="ht_exchange"
        )

        # Create the channel
        channel_factory = ChannelFactory(consumer_instance)
        consumer_channel = channel_factory.get_channel()

        list_message = []
        for method_frame, properties, body in consumer_instance.consume_message(consumer_channel,
                                                                                inactivity_timeout=5):

            if method_frame:
                output_message = json.loads(body.decode('utf-8'))
                list_message.append(output_message)
                consumer_instance.positive_acknowledge(consumer_channel, method_frame.delivery_tag)
                assert len(list_message) == 1
                break
            else:
                logger.warning(f"None method_frame in {consumer_instance.queue_name}... Stopping batch consumption.")
                break



        #producer_instance.ht_channel.queue_purge(producer_instance.queue_name)

    def test_publish_invalid_message_raises_type_error(self, get_rabbit_mq_host_name):

        """Test non-serializable data - Invalid message format"""

        producer_instance = QueueProducer("guest",
                                          "guest",
                                          get_rabbit_mq_host_name,
                                          "test_queue_invalid",
                                          batch_size=1,
                                          exchange_name="ht_exchange"
        )

        class NonSerializable:
            pass

        # Create the channel
        channel_factory = ChannelFactory(producer_instance)
        channel = channel_factory.get_channel()
        with pytest.raises(TypeError):
            producer_instance.publish_messages({"ht_id": "123", "payload": NonSerializable()}, channel)

        # Add close method to ensure the connection is closed after the test
        #channel.close_channel()
        channel_factory.close_channel()

    def test_queue_reconnect(self, get_rabbit_mq_host_name):
        producer_instance = QueueProducer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            "test_queue_reconnect",
            batch_size=1,
            exchange_name="ht_exchange"
        )

        # Check if the connection is open
        assert producer_instance.queue_connection.is_open

        # Create the channel
        channel_factory = ChannelFactory(producer_instance)
        channel = channel_factory.get_channel()

        # Close the connection
        channel_factory.close_channel()

        # Check if the connection is closed
        #assert not producer_instance.is_ready()

        # Reconnect
        #producer_instance.queue_reconnect()

        # Check if the connection is open
        #assert producer_instance.queue_connection.is_open

        #producer_instance.ht_channel.queue_purge(producer_instance.queue_name)
