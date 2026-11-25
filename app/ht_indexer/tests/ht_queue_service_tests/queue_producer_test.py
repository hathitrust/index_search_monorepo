import contextlib
import json
import threading
import time
from collections.abc import Callable
from typing import Any
from unittest.mock import PropertyMock, create_autospec, patch

import pika.exceptions
import pytest
from conftest import QueueTestSettings
from ht_queue_service.queue_connection import QueueConnection
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
from pika.adapters.thread_safe_connection import Channel

logger = get_ht_logger(name=__name__)

message = {"ht_id": "12345678", "ht_title": "Hello World", "ht_author": "John Doe"}
# Compute the message size as QueueProducer.publish_messages
MESSAGE_SIZE = len(json.dumps(message).encode("utf-8"))


@pytest.fixture
def make_producer(
    make_queue_connection: Callable[[QueueTestSettings], QueueConnection],
) -> Callable[..., QueueProducer]:
    def make(**overrides: Any) -> QueueProducer:  # Any: forwards arbitrary QueueParams overrides
        settings = QueueTestSettings(**overrides)
        connection = make_queue_connection(settings)
        producer = QueueProducer(settings, queue_connection=connection)
        assert producer.channel is not None
        producer.channel.queue_purge(producer.queue_manager.queue_name)
        return producer

    return make


class TestQueueProducer:
    """Test the QueueProducer class"""

    def test_producer_uses_given_queue_connection(self, queue_settings: QueueTestSettings) -> None:

        # Use create_autospec to create a realistic mock of QueueConnection that will raise an error if any unexpected methods are called
        # For this test, it ensures that connection.channel is available only after QueueConnection.channel() exists
        connection = create_autospec(QueueConnection, instance=True)
        channel = connection.channel.return_value

        with patch("ht_queue_service.queue_producer.QueueManager.is_ready", return_value=True):
            producer = QueueProducer(queue_settings, queue_connection=connection)

        connection.channel.assert_called_once_with()
        assert producer.channel is channel
    
    @pytest.mark.integration
    def test_queue_produce_one_message(self, make_producer: Callable[..., QueueProducer]) -> None:
        """Test publishing a single message to the queue and consuming it to verify."""

        producer_instance = make_producer()

        producer_instance.publish_messages(message)
        assert producer_instance.channel is not None
        method, _, body = producer_instance.channel.basic_get(
            queue=producer_instance.queue_manager.queue_name, auto_ack=False
        )

        assert method is not None
        assert body is not None
        assert json.loads(body) == message
        producer_instance.channel.basic_ack(delivery_tag=method.delivery_tag)

    @pytest.mark.integration
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

    print(f"Making producer with max message size {limit}")
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
    """Stands in for a pika channel with publisher confirms: no broker needed.
    
    Synchronous mode: the broker reply is replayed inside basic_publish, through the callbacks
    the producer registered. `outcome` picks the reply:
      "ack"    Basic.Ack
      "nack"   Basic.Nack
      "return" Basic.Return, then Basic.Ack (what RabbitMQ sends for a mandatory unroutable publish)
      "none"   no reply (a lost confirm; the producer must time out)
    """

    def __init__(
        self, publish_error: Exception | None = None, confirm_error: Exception | None = None,
            outcome: str = "ack", return_callback_error: Exception | None = None,
    ) -> None:
        self.publish_error = publish_error
        self.confirm_error = confirm_error
        self.return_callback_error = return_callback_error
        self.outcome = outcome
        self.is_closed = False
        self.confirm_enabled = False
        self.publish_calls: list[dict[str, Any]] = []
        self._on_confirm: Callable[[Any], None] | None = None 
        self._on_return: Callable[..., None] | None = None

    def confirm_delivery(
        self, ack_nack_callback: Callable[[Any], None], timeout: float = 10.0
    ) -> None:
        if self.confirm_error is not None:
            raise self.confirm_error
        self._on_confirm = ack_nack_callback
        self.confirm_enabled = True

    def basic_publish(self, **kwargs: Any) -> None:
        self.publish_calls.append(kwargs)
        if self.publish_error is not None:
            raise self.publish_error
        self._replay_broker_reply(kwargs, delivery_tag=len(self.publish_calls))

    def add_on_return_callback(self, callback: Callable[..., None]) -> None:
        if self.return_callback_error is not None:
            raise self.return_callback_error
        self._on_return = callback

    def _replay_broker_reply(self, published: dict[str, Any], delivery_tag: int) -> None:
        assert self._on_confirm is not None and self._on_return is not None
        if self.outcome == "return":
            returned = pika.spec.Basic.Return(
                312, "NO_ROUTE", published["exchange"], published["routing_key"]
            )
            self._on_return(self, returned, published.get("properties"), published["body"])
        if self.outcome in ("ack", "return"):
            self._on_confirm(pika.frame.Method(1, pika.spec.Basic.Ack(delivery_tag=delivery_tag)))
        elif self.outcome == "nack":
            self._on_confirm(pika.frame.Method(1, pika.spec.Basic.Nack(delivery_tag=delivery_tag)))


@pytest.fixture
def make_fake_producer(
    queue_settings: QueueTestSettings,
) -> Callable[..., tuple[QueueProducer, FakeChannel, Any]]:
    """Build a producer with a fake channel and a mocked QueueConnection."""

    def _make(publish_error: Exception | None = None, outcome: str = "ack") -> tuple[QueueProducer, FakeChannel, Any]:
        channel = FakeChannel(publish_error, outcome=outcome)
        connection = create_autospec(QueueConnection, instance=True)
        connection.channel.return_value = channel
        with patch.object(QueueManager, "is_ready", return_value=True):
            producer = QueueProducer(queue_settings, queue_connection=connection)
        return producer, channel, connection.channel

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


def test_thread_channel_that_cannot_be_opened_raises_publish_connection_error(
    make_fake_producer: Callable[..., tuple[QueueProducer, FakeChannel, Any]],
) -> None:
    """QueueConnection.channel wraps pika errors in RuntimeError: callers still get our type."""
    producer, _, get_channel = make_fake_producer()
    get_channel.side_effect = RuntimeError("Failed to create channel: boom")
    errors: list[Exception] = []

    def publish() -> None:
        try:
            producer.publish_messages(message)
        except Exception as err:
            errors.append(err)

    worker = threading.Thread(target=publish)
    worker.start()
    worker.join()

    assert len(errors) == 1
    assert type(errors[0]) is PublishConnectionError
    assert isinstance(errors[0].__cause__, RuntimeError)


class TestProducerStartup:
    """Errors while the producer is built must also be our own type, never pika's or RuntimeError."""

    @pytest.mark.parametrize(
        ("channel_error", "confirm_error", "set_up_error"),
        [
            pytest.param(
                RuntimeError("Failed to create channel"), None, None, id="channel-runtime-error"
            ),
            pytest.param(
                None, pika.exceptions.ChannelWrongStateError("closing"), None, id="confirm-fails"
            ),
            pytest.param(
                None,
                None,
                pika.exceptions.ChannelClosedByBroker(406, "PRECONDITION_FAILED"),
                id="set-up-fails",
            ),
            pytest.param(
                pika.exceptions.AMQPConnectionError("refused"), None, None, id="connection-refused"
            ),
        ],
    )
    def test_startup_failure_raises_publish_connection_error(
        self,
        queue_settings: QueueTestSettings,
        channel_error: Exception | None,
        confirm_error: Exception | None,
        set_up_error: Exception | None,
    ) -> None:
        channel = FakeChannel(confirm_error=confirm_error)
        connection = create_autospec(QueueConnection, instance=True)
        with (
            patch.object(QueueManager, "is_ready", return_value=set_up_error is None),
            patch.object(QueueManager, "set_up_queue", side_effect=set_up_error),
        ):
            get_channel = connection.channel
            if channel_error is not None:
                get_channel.side_effect = channel_error
            else:
                get_channel.return_value = channel
            with pytest.raises(PublishConnectionError) as raised:
                QueueProducer(queue_settings, queue_connection=connection)

        assert type(raised.value) is PublishConnectionError
        assert raised.value.__cause__ is not None


@pytest.mark.integration
def test_publish_messages_lost_channel_raises_and_does_not_reconnect(
    make_producer: Callable[..., QueueProducer],
) -> None:
    producer = make_producer()
    original_channel = producer.channel

    with (
        patch.object(Channel, "is_closed", new_callable=PropertyMock, return_value=True),
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

    try:
        with pytest.raises(PublishUnroutableError):
            producer.publish_messages(message)
    finally:
        producer.channel.queue_bind(
            queue=manager.queue_name,
            exchange=manager.main_exchange_name,
            routing_key=manager.queue_name,
        )
