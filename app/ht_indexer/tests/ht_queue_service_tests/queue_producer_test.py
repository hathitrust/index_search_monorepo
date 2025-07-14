import pytest

from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

message = {"ht_id": "12345678", "ht_title": "Hello World", "ht_author": "John Doe"}

class TestQueueProducer:
    def test_queue_produce_one_message(self, get_rabbit_mq_host_name):
        producer_instance = QueueProducer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            "test_queue_produce_one_message",
            batch_size=1
        )

        producer_instance.ht_channel.queue_purge(producer_instance.queue_name)

        producer_instance.publish_messages(message)
        assert producer_instance.get_total_messages() == 1

        producer_instance.ht_channel.queue_purge(producer_instance.queue_name)

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

        # Close the connection
        producer_instance.close()

        # Check if the connection is closed
        assert not producer_instance.is_ready()

        # Reconnect
        producer_instance.queue_reconnect()

        # Check if the connection is open
        assert producer_instance.queue_connection.is_open

        producer_instance.ht_channel.queue_purge(producer_instance.queue_name)
