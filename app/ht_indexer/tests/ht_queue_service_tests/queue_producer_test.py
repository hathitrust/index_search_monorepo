import contextlib
import json
import threading
import time
from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import PropertyMock, patch

import pika.exceptions
import pytest
from conftest import ConcreteQueueConsumer, close_channel_and_connection
from ht_queue_service.queue_config import QueueConfig
from ht_queue_service.queue_manager import QueueManager
from ht_queue_service.queue_producer import (
    MessageTooLargeError,
    PublishConnectionError,
    PublishError,
    PublishRefusedError,
    PublishUnroutableError,
    QueueProducer,
)
from ht_utils.ht_logger import get_ht_logger
from ht_utils.testing import assert_log_entry, capture_logs
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

    for _ in range(20):
        total = producer.queue_manager.get_total_messages(producer.channel)
        if total == published:
            break
        time.sleep(0.1)
    assert total == published


@pytest.mark.integration
def test_publish_messages_published_logs_message_size(
    make_producer: Callable[..., QueueProducer],
) -> None:
    producer = make_producer()

    with capture_logs() as entries:
        producer.publish_messages(message)

        assert_log_entry(entries, size=MESSAGE_SIZE)


@pytest.mark.integration
@pytest.mark.parametrize(
    "queue_message",
    [
        pytest.param({"ht_id": "12345678"}, id="retriever-message-ht-id-key"),
        pytest.param({"id": "12345678"}, id="generator-solr-document-id-key"),
    ],
)
def test_publish_messages_published_logs_ht_id(
    make_producer: Callable[..., QueueProducer],
    queue_message: dict[str, str],
) -> None:
    producer = make_producer()

    with capture_logs() as entries:
        producer.publish_messages(queue_message)

    assert_log_entry(entries, ht_id="12345678")


@pytest.mark.integration
def test_publish_messages_serialization_failure_logs_ht_id_as_a_field(
    make_producer: Callable[..., QueueProducer],
) -> None:
    producer = make_producer()

    with capture_logs() as entries, pytest.raises(TypeError):
        producer.publish_messages({"id": "mdp.1", "not_json": object()})

    assert_log_entry(entries, event="Failed to serialize message", log_level="error", ht_id="mdp.1")


@pytest.mark.integration
def test_publish_messages_too_large_logs_ht_id_as_a_field(
    make_producer: Callable[..., QueueProducer],
) -> None:
    producer = make_producer(max_message_size=MESSAGE_SIZE - 1)

    with capture_logs() as entries, pytest.raises(MessageTooLargeError):
        producer.publish_messages({"id": "mdp.1", "text": "x" * MESSAGE_SIZE})

    assert_log_entry(
        entries,
        event="Message too large, not published",
        log_level="error",
        ht_id="mdp.1",
        limit=MESSAGE_SIZE - 1,
    )


class FakeChannel:
    """Stands in for a pika channel with publisher confirms: no broker needed."""

    def __init__(self, publish_error: Exception | None = None) -> None:
        self.publish_error = publish_error
        self.is_closed = False
        self.confirm_enabled = False
        self.publish_calls: list[dict[str, Any]] = []

    def confirm_delivery(self) -> None:
        self.confirm_enabled = True

    def basic_publish(self, **kwargs: Any) -> None:  # Any: mirrors pika's keyword arguments
        self.publish_calls.append(kwargs)
        if self.publish_error is not None:
            raise self.publish_error


@pytest.fixture
def make_fake_producer(
    make_queue_config: Callable[..., QueueConfig],
) -> Callable[..., tuple[QueueProducer, FakeChannel, Any]]:
    """Build a QueueProducer whose channel is a FakeChannel. Returns (producer, channel, get_channel mock)."""

    def _make(publish_error: Exception | None = None) -> tuple[QueueProducer, FakeChannel, Any]:
        channel = FakeChannel(publish_error)
        with (
            patch("ht_queue_service.queue_producer.ChannelCreator") as channel_creator,
            patch.object(QueueManager, "is_ready", return_value=True),
        ):
            channel_creator.return_value.get_channel.return_value = channel
            producer = QueueProducer(make_queue_config(batch_size=1).queue_params)
        return producer, channel, channel_creator.return_value.get_channel

    return _make


class TestPublishWithFakeChannel:
    def test_confirmed_publish_returns_and_is_mandatory(
        self, make_fake_producer: Callable[..., tuple[QueueProducer, FakeChannel, Any]]
    ) -> None:
        """Broker ack: publish_messages returns normally, after confirms were turned on."""
        producer, channel, _ = make_fake_producer()

        producer.publish_messages(message)

        assert channel.confirm_enabled
        assert len(channel.publish_calls) == 1
        assert channel.publish_calls[0]["mandatory"] is True
        assert channel.publish_calls[0]["routing_key"] == producer.queue_manager.queue_name

    @pytest.mark.parametrize(
        ("pika_error", "expected_error"),
        [
            pytest.param(pika.exceptions.NackError([]), PublishRefusedError, id="nack"),
            pytest.param(pika.exceptions.UnroutableError([]), PublishUnroutableError, id="return"),
            pytest.param(
                pika.exceptions.ChannelClosed(406, "PRECONDITION_FAILED"),
                PublishConnectionError,
                id="channel-closed",
            ),
            pytest.param(
                pika.exceptions.ConnectionClosed(320, "CONNECTION_FORCED"),
                PublishConnectionError,
                id="connection-closed",
            ),
            pytest.param(
                pika.exceptions.StreamLostError("socket"), PublishConnectionError, id="stream-lost"
            ),
            pytest.param(
                pika.exceptions.ChannelWrongStateError("closing"),
                PublishConnectionError,
                id="channel-wrong-state",
            ),
        ],
    )
    def test_publish_failure_raises_our_error_without_retry_or_reconnect(
        self,
        make_fake_producer: Callable[..., tuple[QueueProducer, FakeChannel, Any]],
        pika_error: Exception,
        expected_error: type[PublishError],
    ) -> None:
        producer, channel, get_channel = make_fake_producer(pika_error)

        with pytest.raises(expected_error) as raised:
            producer.publish_messages(message)

        assert type(raised.value) is expected_error
        assert raised.value.__cause__ is pika_error  # the pika error is kept as the cause only
        assert len(channel.publish_calls) == 1  # no retry
        assert get_channel.call_count == 1  # no reconnect: the channel was opened once, in __init__

    def test_closed_channel_raises_connection_error_without_publishing(
        self, make_fake_producer: Callable[..., tuple[QueueProducer, FakeChannel, Any]]
    ) -> None:
        producer, channel, get_channel = make_fake_producer()
        channel.is_closed = True

        with pytest.raises(PublishConnectionError):
            producer.publish_messages(message)

        assert channel.publish_calls == []
        assert get_channel.call_count == 1


def test_thread_channel_is_dropped_after_a_failure_and_opened_again_next_time(
    make_fake_producer: Callable[..., tuple[QueueProducer, FakeChannel, Any]],
) -> None:
    """A closed thread channel must not make every later publish from that thread fail."""
    producer, _, get_channel = make_fake_producer()
    broken = FakeChannel(pika.exceptions.ChannelClosed(406, "PRECONDITION_FAILED"))
    healthy = FakeChannel()
    get_channel.side_effect = [broken, healthy]
    results: list[Any] = []

    def publish_twice() -> None:
        for _ in range(2):
            try:
                producer.publish_messages(message)
                results.append("published")
            except PublishConnectionError:
                results.append("connection-error")

    with patch.object(QueueManager, "set_up_queue"):
        worker = threading.Thread(target=publish_twice)
        worker.start()
        worker.join()

    assert results == ["connection-error", "published"]
    assert len(healthy.publish_calls) == 1


@pytest.mark.integration
def test_publish_messages_lost_channel_raises_and_does_not_reconnect(
    make_producer: Callable[..., QueueProducer],
) -> None:
    producer = make_producer()
    original_channel = producer.channel

    with (
        patch.object(BlockingChannel, "is_closed", new_callable=PropertyMock, return_value=True),
        pytest.raises(PublishConnectionError),
    ):
        producer.publish_messages(message)

    assert producer.channel is original_channel  # the producer did not open a new channel


@pytest.mark.integration
def test_publish_messages_unroutable_raises_instead_of_losing_the_message(
    make_producer: Callable[..., QueueProducer],
) -> None:
    """Against RabbitMQ: with the binding removed, mandatory=True makes the broker return the message."""
    producer = make_producer()
    manager = producer.queue_manager
    assert producer.channel is not None
    producer.channel.queue_unbind(
        queue=manager.queue_name,
        exchange=manager.main_exchange_name,
        routing_key=manager.queue_name,
    )

    with pytest.raises(PublishUnroutableError):
        producer.publish_messages(message)
