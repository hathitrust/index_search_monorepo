import contextlib
import json
import logging
from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import patch

import pika.exceptions
import pytest
from conftest import ConcreteQueueConsumer, close_channel_and_connection
from ht_queue_service.queue_config import QueueConfig
from ht_queue_service.queue_producer import MessageTooLargeError, QueueProducer
from ht_utils.ht_logger import get_ht_logger
from pika.adapters.blocking_connection import BlockingChannel

logger = get_ht_logger(name=__name__)

message = {"ht_id": "12345678", "ht_title": "Hello World", "ht_author": "John Doe"}
# Compute the message size as QueueProducer.publish_messages
MESSAGE_SIZE = len(json.dumps(message).encode("utf-8"))


@pytest.fixture
def make_producer(
    make_queue_config: Callable[..., QueueConfig],
) -> Generator[Callable[..., QueueProducer]]:
    producers: list[QueueProducer] = []

    def _make(**overrides: Any) -> QueueProducer:  # Any: forwards arbitrary QueueParams overrides
        producer = QueueProducer(make_queue_config(batch_size=1, **overrides).queue_params)
        producers.append(producer)
        return producer

    yield _make
    for producer in producers:
        close_channel_and_connection(producer)


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
        consumer_instance = ConcreteQueueConsumer(producer_queue_config.queue_params)

        list_message: list[dict[str, Any]] = []
        assert consumer_instance.channel is not None
        for method_frame, _, body in consumer_instance.consume_dead_letter_messages(
            consumer_instance.channel,
            inactivity_timeout=5,
            queue_name=consumer_instance.queue_manager.queue_name,
        ):
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
        self, make_producer: Callable[..., QueueProducer]
    ) -> None:
        """Test non-serializable data - Invalid message format"""
        producer_instance = make_producer()

        class NonSerializable:
            pass

        with pytest.raises(TypeError):
            producer_instance.publish_messages({"ht_id": "123", "payload": NonSerializable()})

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


@pytest.mark.integration
@pytest.mark.parametrize(
    ("limit", "expectation", "published"),
    [
        pytest.param(
            MESSAGE_SIZE - 1,
            pytest.raises(MessageTooLargeError, match="exceeds max_message_size"),
            0,
            id="over-limit-not-published",
        ),
        pytest.param(MESSAGE_SIZE, contextlib.nullcontext(), 1, id="at-limit-published"),
    ],
)
def test_publish_messages_max_message_size_limits_what_is_published(
    make_producer: Callable[..., QueueProducer],
    limit: int,
    expectation: contextlib.AbstractContextManager[Any],
    published: int,
) -> None:
    """Check if the producer publishes a message only if its serialized size is less than or equal to max_message_size"""

    producer = make_producer(max_message_size=limit)

    with expectation:
        producer.publish_messages(message)
    #           Case           │             limit             │           expectation           │        published
    # over-limit-not-published │ 1 byte below the message size │ must raise MessageTooLargeError │ 0 messages in the queue
    # at-limit-published       │ exactly the message size      │ must not raise                  │ 1 message in the queue
    assert producer.channel is not None
    assert producer.queue_manager.get_total_messages(producer.channel) == published


@pytest.mark.integration
def test_publish_messages_published_logs_message_size(
    make_producer: Callable[..., QueueProducer], caplog: pytest.LogCaptureFixture
) -> None:
    producer = make_producer()

    with caplog.at_level(logging.INFO):
        producer.publish_messages(message)

    assert f"Size={MESSAGE_SIZE} bytes" in caplog.text


@pytest.mark.integration
@pytest.mark.parametrize(
    ("side_effect", "expectation", "calls"),
    [
        pytest.param(
            pika.exceptions.ChannelClosed(406, "PRECONDITION_FAILED"),
            pytest.raises(pika.exceptions.ChannelClosed),
            3,
            id="always-closed-gives-up",
        ),
        pytest.param(
            [pika.exceptions.ChannelClosed(406, "x"), None],
            contextlib.nullcontext(),
            2,
            id="closed-once-recovers",
        ),
    ],
)
def test_publish_messages_channel_closed_retries_at_most_three_attempts(
    make_producer: Callable[..., QueueProducer],
    side_effect: Any,  # Any: pika side_effect may be a single exception or a list
    expectation: contextlib.AbstractContextManager[Any],
    calls: int,
) -> None:
    """Checks that when publishing fails because the channel or connection closed, the producer reconnects and retries, and gives up after at most MAX_PUBLISH_ATTEMPTS (3) attempts."""
    producer = make_producer()

    with (
        patch.object(BlockingChannel, "basic_publish", side_effect=side_effect) as basic_publish,
        expectation,
    ):
        producer.publish_messages(message)

    assert basic_publish.call_count == calls
