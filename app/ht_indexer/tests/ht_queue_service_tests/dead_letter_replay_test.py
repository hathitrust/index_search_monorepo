import json
import time
from types import SimpleNamespace
from typing import Any, NamedTuple, cast
from unittest.mock import MagicMock

import pika
import pytest
from conftest import ConcreteQueueConsumer, QueueTestSettings, close_channel_and_connection
from ht_queue_service.dead_letter_replay import ReplaySummary, replay_dead_letter_messages
from ht_utils.testing import assert_log_entry, capture_logs
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import NackError, UnroutableError


def _body(ht_id: str) -> bytes:
    return json.dumps({"id": ht_id}).encode()


class PublishedMessage(NamedTuple):
    exchange: str
    routing_key: str
    body: bytes
    mandatory: bool


class FakeChannel:
    """A RabbitMQ channel whose dead-letter queue is a list, for the replay tests.

    `dead_letters` are the bodies waiting in the dead-letter queue. A message that was read with
    basic_get stays "unacked" until it is acked, or nacked with requeue (then it goes back to the
    front of `dead_letters`). Delivery tags are 1, 2, 3... for every message read.

    It answers like RabbitMQ does, so a replay that forgets a safety setting fails here:
    - a refusal of the broker (`NackError`) is only seen when confirm_delivery() was called
    - an unroutable message (`UnroutableError`) is only seen with confirm_delivery() and
      mandatory=True. Otherwise the message is dropped silently.

    :param publish_errors: Maps the number of a basic_publish call (1 is the first) to the error
        the broker gives for it
    :param nack_error: Error raised by basic_nack, like a channel that has closed
    :param dead_letter_again: Every message that is published fails in its consumer and comes
        back to the dead-letter queue
    """

    def __init__(
        self,
        dead_letters: list[bytes],
        publish_errors: dict[int, Exception] | None = None,
        nack_error: Exception | None = None,
        dead_letter_again: bool = False,
    ) -> None:
        self.dead_letters = list(dead_letters)
        self.publish_errors = publish_errors or {}
        self.nack_error = nack_error
        self.dead_letter_again = dead_letter_again
        self.confirms_enabled = False
        self.published: list[PublishedMessage] = []
        self.acked: list[int] = []
        self.get_count = 0
        self.unacked: dict[int, bytes] = {}
        self._publish_count = 0
        self._next_tag = 1

    def queue_declare(self, queue: str, passive: bool = False) -> SimpleNamespace:
        return SimpleNamespace(method=SimpleNamespace(message_count=len(self.dead_letters)))

    def confirm_delivery(self) -> None:
        self.confirms_enabled = True

    def basic_get(
        self, queue: str, auto_ack: bool = False
    ) -> tuple[SimpleNamespace | None, None, bytes | None]:
        self.get_count += 1
        if not self.dead_letters:
            return None, None, None
        delivery_tag = self._next_tag
        self._next_tag += 1
        body = self.dead_letters.pop(0)
        self.unacked[delivery_tag] = body
        return SimpleNamespace(delivery_tag=delivery_tag), None, body

    def basic_publish(
        self,
        exchange: str,
        routing_key: str,
        body: bytes,
        properties: pika.BasicProperties | None = None,
        mandatory: bool = False,
    ) -> None:
        self._publish_count += 1
        error = self.publish_errors.get(self._publish_count)
        if error is not None:
            seen_by_the_caller = self.confirms_enabled and (
                mandatory or not isinstance(error, UnroutableError)
            )
            if isinstance(error, NackError | UnroutableError) and not seen_by_the_caller:
                return  # The broker lost the message and nobody was told
            raise error
        self.published.append(PublishedMessage(exchange, routing_key, body, mandatory))
        if self.dead_letter_again:
            self.dead_letters.append(body)

    def basic_ack(self, delivery_tag: int) -> None:
        del self.unacked[delivery_tag]
        self.acked.append(delivery_tag)

    def basic_nack(self, delivery_tag: int, multiple: bool = False, requeue: bool = True) -> None:
        if self.nack_error is not None:
            raise self.nack_error
        tags = sorted(
            t for t in self.unacked if (t <= delivery_tag if multiple else t == delivery_tag)
        )
        returned = [self.unacked.pop(tag) for tag in tags]
        if requeue:
            self.dead_letters[0:0] = returned


def _queue_manager() -> MagicMock:
    return MagicMock(
        queue_name="indexer_queue",
        main_exchange_name="indexer_queue_exchange",
        dead_letter_queue_name="indexer_queue_dlq",
    )


def _replay(channel: FakeChannel, **options: Any) -> ReplaySummary:
    return replay_dead_letter_messages(cast(BlockingChannel, channel), _queue_manager(), **options)


def test_replay_publishes_to_the_main_queue_then_acknowledges_the_dead_letter() -> None:
    channel = FakeChannel([_body("a"), _body("b")])

    summary = _replay(channel)

    assert summary.replayed == 2
    assert [(m.exchange, m.routing_key, m.body) for m in channel.published] == [
        ("indexer_queue_exchange", "indexer_queue", _body("a")),
        ("indexer_queue_exchange", "indexer_queue", _body("b")),
    ]
    assert channel.acked == [1, 2]
    assert channel.dead_letters == []
    assert channel.unacked == {}


def test_replay_waits_for_the_broker_to_confirm_and_marks_messages_mandatory() -> None:
    channel = FakeChannel([_body("a")])

    _replay(channel)

    assert channel.confirms_enabled
    assert all(message.mandatory for message in channel.published)


def test_replay_logs_structured_events_with_the_ht_id_as_a_field() -> None:
    channel = FakeChannel([_body("mdp.1")])

    with capture_logs() as entries:
        _replay(channel)

    assert_log_entry(
        entries, event="dlq_replay_started", queue="indexer_queue_dlq", in_dead_letter_queue=1
    )
    assert_log_entry(entries, event="dlq_replay_message", ht_id="mdp.1")
    assert_log_entry(entries, event="dlq_replay_finished", replayed=1, inspected=1, dry_run=False)


def test_a_failed_replay_logs_the_ht_id_and_the_error_as_fields() -> None:
    channel = FakeChannel(
        [_body("mdp.1")], publish_errors={1: pika.exceptions.ChannelClosed(320, "gone")}
    )

    with capture_logs() as entries, pytest.raises(pika.exceptions.ChannelClosed):
        _replay(channel)

    assert_log_entry(entries, event="dlq_replay_failed", ht_id="mdp.1", replayed=0)


def test_replay_respects_max() -> None:
    channel = FakeChannel([_body("a"), _body("b"), _body("c")])

    summary = _replay(channel, max_messages=2)

    assert summary.replayed == 2
    assert len(channel.published) == 2
    assert channel.dead_letters == [_body("c")]


def test_replay_stops_at_the_starting_count_even_if_messages_keep_arriving() -> None:
    """A replayed message that fails again is dead-lettered again; that must not extend the run."""
    channel = FakeChannel([_body("a")], dead_letter_again=True)

    summary = _replay(channel)

    assert summary.replayed == 1
    assert channel.get_count == 1
    assert channel.dead_letters == [_body("a")]


def test_replay_of_an_empty_dead_letter_queue_does_nothing() -> None:
    channel = FakeChannel([])

    summary = _replay(channel)

    assert summary.replayed == 0
    assert channel.published == []


def test_dry_run_publishes_nothing_and_hands_every_message_back() -> None:
    channel = FakeChannel([_body("a"), _body("b")])

    summary = _replay(channel, dry_run=True)

    assert summary.replayed == 0
    assert summary.inspected == 2
    assert channel.published == []
    assert channel.acked == []
    assert not channel.confirms_enabled
    # Both messages are back in the dead-letter queue, in the same order
    assert channel.dead_letters == [_body("a"), _body("b")]
    assert channel.unacked == {}


@pytest.mark.parametrize(
    "error", [UnroutableError([]), NackError([]), pika.exceptions.ChannelClosed(320, "gone")]
)
def test_failed_publish_leaves_the_message_in_the_dead_letter_queue_and_stops(
    error: Exception,
) -> None:
    channel = FakeChannel([_body("a"), _body("b"), _body("c")], publish_errors={2: error})

    with pytest.raises(type(error)):
        _replay(channel)

    assert channel.acked == [1]
    # The failed message is back at the front; the third message was never touched
    assert channel.dead_letters == [_body("b"), _body("c")]
    assert channel.unacked == {}
    assert channel.get_count == 2


def test_replay_moves_a_dead_lettered_message_back_to_the_main_queue() -> None:
    """With a real RabbitMQ: reject a message so the broker dead-letters it, then replay it."""
    queue_settings = QueueTestSettings()
    consumer = ConcreteQueueConsumer(queue_settings)
    assert consumer.channel is not None
    channel = consumer.channel
    queue_manager = consumer.queue_manager
    message: dict[str, Any] = {"id": "mdp.123", "ht_title": "Hello"}

    try:
        consumer.queue_manager.set_up_queue(channel)
        channel.queue_purge(queue_manager.queue_name)
        channel.queue_purge(queue_manager.dead_letter_queue_name)

        channel.basic_publish(
            exchange=queue_manager.main_exchange_name,
            routing_key=queue_manager.queue_name,
            body=json.dumps(message).encode(),
        )
        method_frame, _, _ = channel.basic_get(queue_manager.queue_name, auto_ack=False)
        assert method_frame is not None
        assert method_frame.delivery_tag is not None
        consumer.dead_letter_message(channel, method_frame.delivery_tag)

        # The broker moves it to the dead-letter queue right away; wait briefly to be sure
        for _ in range(20):
            count = channel.queue_declare(queue_manager.dead_letter_queue_name, passive=True)
            if count.method.message_count == 1:
                break
            time.sleep(0.1)
        assert count.method.message_count == 1

        summary = replay_dead_letter_messages(channel, queue_manager)

        assert summary.replayed == 1
        assert (
            channel.queue_declare(
                queue_manager.dead_letter_queue_name, passive=True
            ).method.message_count
            == 0
        )
        _, _, body = channel.basic_get(queue_manager.queue_name, auto_ack=True)
        assert body is not None
        assert json.loads(body) == message
    finally:
        channel.queue_purge(queue_manager.queue_name)
        channel.queue_purge(queue_manager.dead_letter_queue_name)
        close_channel_and_connection(consumer)


def test_a_failing_nack_does_not_hide_the_original_publish_error() -> None:
    channel = FakeChannel(
        [_body("a")],
        publish_errors={1: pika.exceptions.ChannelClosed(320, "gone")},
        nack_error=pika.exceptions.ChannelWrongStateError("closed"),
    )

    with pytest.raises(pika.exceptions.ChannelClosed):
        _replay(channel)
