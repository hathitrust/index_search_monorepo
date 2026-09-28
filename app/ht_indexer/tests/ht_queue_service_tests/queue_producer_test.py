import json
from collections.abc import Callable
from typing import Any

import pytest
from conftest import close_channel_and_connection
from ht_queue_service.queue_config import QueueConfig
from ht_queue_service.queue_consumer import QueueConsumer
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

message = {"ht_id": "12345678", "ht_title": "Hello World", "ht_author": "John Doe"}


class TestQueueProducer:
    """Test the QueueProducer class"""

    def test_queue_produce_one_message(self, make_queue_config: Callable[..., QueueConfig]) -> None:
        """Test publishing a single message to the queue and consuming it to verify."""
        producer_queue_config = make_queue_config(batch_size=1, requeue_message=False)

        producer_instance = QueueProducer(producer_queue_config.queue_params)

        producer_instance.publish_messages(message)
        assert producer_instance.channel is not None
        producer_instance.channel.close()

        # Consume the message to ensure it was published correctly
        consumer_instance = QueueConsumer(producer_queue_config.queue_params)

        list_message: list[dict[str, Any]] = []
        for method_frame, _, body in consumer_instance.consume_message(inactivity_timeout=5):
            if method_frame:
                output_message = json.loads(body.decode("utf-8"))
                list_message.append(output_message)
                assert consumer_instance.channel is not None
                consumer_instance.positive_acknowledge(
                    consumer_instance.channel, method_frame.delivery_tag
                )
                assert len(list_message) == 1
                break
            else:
                logger.warning(
                    f"None method_frame in {consumer_instance.queue_manager.queue_name}... Stopping batch consumption."
                )
                break

    def test_publish_invalid_message_raises_type_error(
        self, make_queue_config: Callable[..., QueueConfig]
    ) -> None:
        """Test non-serializable data - Invalid message format"""
        producer_queue_config = make_queue_config(batch_size=1, requeue_message=False)

        producer_instance = QueueProducer(producer_queue_config.queue_params)

        class NonSerializable:
            pass

        with pytest.raises(TypeError):
            producer_instance.publish_messages({"ht_id": "123", "payload": NonSerializable()})

        close_channel_and_connection(producer_instance)

    def test_queue_reconnect(self, make_queue_config: Callable[..., QueueConfig]) -> None:
        """Test the queue reconnect functionality of the QueueProducer class"""
        producer_queue_config = make_queue_config(batch_size=1, requeue_message=False)

        producer_instance = QueueProducer(producer_queue_config.queue_params)

        # Check if the connection is open
        assert producer_instance.channel_creator.connection.queue_connection is not None
        assert producer_instance.channel_creator.connection.queue_connection.is_open
        assert producer_instance.channel is not None
        assert producer_instance.channel.is_open

        # Close the channel
        producer_instance.channel.close()

        assert producer_instance.channel.is_closed

        producer_instance.queue_reconnect()

        assert producer_instance.channel is not None
        assert producer_instance.channel.is_open

        close_channel_and_connection(producer_instance)
