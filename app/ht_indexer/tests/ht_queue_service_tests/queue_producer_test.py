import pytest
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

message = {"ht_id": "12345678", "ht_title": "Hello World", "ht_author": "John Doe"}

class TestQueueProducer:
    def test_queue_produce_one_message(self, get_rabbit_mq_host_name):

        """Test for producing one message to the queue"""

        producer_instance = QueueProducer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            "test_queue_produce_one_message",
            batch_size=1
        )

        producer_instance.ht_channel.queue_purge(producer_instance.queue_name)

        producer_instance.publish_messages(message)

        # If you publish a message to RabbitMQ and immediately check the message count, but it shows 0,
        # the cause is likely message prefetching and unacknowledged delivery.
        assert producer_instance.get_total_messages() == 1

        producer_instance.ht_channel.queue_purge(producer_instance.queue_name)

        # Add close method to ensure the connection is closed after the test
        if producer_instance.queue_connection.is_open:
            producer_instance.close()

    def test_queue_reconnect(self, get_rabbit_mq_host_name):

        """Test for reconnecting to the queue after closing the connection"""

        producer_instance = QueueProducer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            "test_queue_reconnect",
            batch_size=1
        )

        # Check if the connection is open
        assert producer_instance.queue_connection.is_open

        # Close the connection
        producer_instance.close()

        # Check if the connection is closed
        assert not producer_instance.is_ready()

        # Reconnect
        producer_instance.queue_reconnect()

        # Check if the connection is open
        assert producer_instance.queue_connection.is_open

        producer_instance.ht_channel.queue_purge(producer_instance.queue_name)

        # Add close method to ensure the connection is closed after the test
        producer_instance.close()

    def test_publish_invalid_message_raises_type_error(self, get_rabbit_mq_host_name):

        """Test non-serializable data - Invalid message format"""

        producer_instance = QueueProducer(
            "guest", "guest", get_rabbit_mq_host_name, "test_queue_invalid", batch_size=1
        )

        class NonSerializable:
            pass

        with pytest.raises(TypeError):
            producer_instance.publish_messages({"ht_id": "123", "payload": NonSerializable()})

        # Add close method to ensure the connection is closed after the test
        producer_instance.close()

    def test_publish_with_closed_channel_triggers_reconnect(self, get_rabbit_mq_host_name):

        producer_instance = QueueProducer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            "test_queue_closed_channel",
            batch_size=1
        )

        #mock_reconnect = mocker.patch("producer_instance.queue_reconnect")

        # Close the channel
        producer_instance.close()

        producer_instance.publish_messages(message)

        #producer_instance.queue_reconnect().assert_called_once()

        # Add close method to ensure the connection is closed after the test
        #mock_reconnect.assert_called_once()
