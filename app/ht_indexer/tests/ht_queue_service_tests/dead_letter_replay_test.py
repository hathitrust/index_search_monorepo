import json
import time
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pika
import pytest
from conftest import ConcreteQueueConsumer, close_channel_and_connection
from ht_queue_service.dead_letter_replay import replay_dead_letter_messages
from ht_queue_service.queue_config import QueueConfig
from pika.exceptions import NackError, UnroutableError


def _body(ht_id: str) -> bytes:
    return json.dumps({"ht_id": ht_id}).encode()


def _fake_broker(bodies: list[bytes]) -> tuple[MagicMock, MagicMock]:
    """A channel whose dead-letter queue holds `bodies`, and a queue manager with fixed names."""
    queue_manager = MagicMock(
        queue_name="indexer_queue",
        main_exchange_name="indexer_queue_exchange",
        dead_letter_queue_name="indexer_queue_dlq",
    )
    channel = MagicMock()
    channel.queue_declare.return_value = MagicMock(method=MagicMock(message_count=len(bodies)))
    # Delivery tags are 1, 2, 3...; an empty queue answers (None, None, None)
    channel.basic_get.side_effect = [
        (MagicMock(delivery_tag=tag), MagicMock(), body) for tag, body in enumerate(bodies, 1)
    ] + [(None, None, None)] * 5
    return channel, queue_manager


def test_replay_publishes_to_the_main_queue_then_acknowledges_the_dead_letter() -> None:
    channel, queue_manager = _fake_broker([_body("a"), _body("b")])

    summary = replay_dead_letter_messages(channel, queue_manager)

    assert (summary.in_dead_letter_queue, summary.replayed, summary.inspected) == (2, 2, 2)
    publishes = channel.basic_publish.call_args_list
    assert [call.kwargs["exchange"] for call in publishes] == ["indexer_queue_exchange"] * 2
    assert [call.kwargs["routing_key"] for call in publishes] == ["indexer_queue"] * 2
    assert [call.kwargs["body"] for call in publishes] == [_body("a"), _body("b")]
    assert all(call.kwargs["mandatory"] is True for call in publishes)
    assert [call.kwargs["delivery_tag"] for call in channel.basic_ack.call_args_list] == [1, 2]
    channel.confirm_delivery.assert_called_once()
    channel.basic_nack.assert_not_called()
    # Only looked at the dead-letter queue, never created it
    assert channel.queue_declare.call_args.kwargs == {
        "queue": "indexer_queue_dlq",
        "passive": True,
    }


def test_replay_respects_max() -> None:
    channel, queue_manager = _fake_broker([_body("a"), _body("b"), _body("c")])

    summary = replay_dead_letter_messages(channel, queue_manager, max_messages=2)

    assert (summary.in_dead_letter_queue, summary.replayed) == (3, 2)
    assert channel.basic_publish.call_count == 2
    assert channel.basic_get.call_count == 2


def test_replay_stops_at_the_starting_count_even_if_messages_keep_arriving() -> None:
    """A replayed message that fails again is dead-lettered again; that must not extend the run."""
    channel, queue_manager = _fake_broker([_body("a")])
    channel.basic_get.side_effect = [
        (MagicMock(delivery_tag=tag), MagicMock(), _body("a")) for tag in range(1, 50)
    ]

    summary = replay_dead_letter_messages(channel, queue_manager)

    assert summary.replayed == 1
    assert channel.basic_get.call_count == 1


def test_replay_of_an_empty_dead_letter_queue_does_nothing() -> None:
    channel, queue_manager = _fake_broker([])

    summary = replay_dead_letter_messages(channel, queue_manager)

    assert (summary.in_dead_letter_queue, summary.replayed) == (0, 0)
    channel.basic_get.assert_not_called()
    channel.basic_publish.assert_not_called()


def test_dry_run_publishes_nothing_and_hands_every_message_back() -> None:
    channel, queue_manager = _fake_broker([_body("a"), _body("b")])

    summary = replay_dead_letter_messages(channel, queue_manager, dry_run=True)

    assert (summary.in_dead_letter_queue, summary.replayed, summary.inspected) == (2, 0, 2)
    channel.basic_publish.assert_not_called()
    channel.basic_ack.assert_not_called()
    channel.confirm_delivery.assert_not_called()
    channel.basic_nack.assert_called_once_with(delivery_tag=2, multiple=True, requeue=True)


@pytest.mark.parametrize(
    "error", [UnroutableError([]), NackError([]), pika.exceptions.ChannelClosed(320, "gone")]
)
def test_failed_publish_leaves_the_message_in_the_dead_letter_queue_and_stops(
    error: Exception,
) -> None:
    channel, queue_manager = _fake_broker([_body("a"), _body("b"), _body("c")])
    # The first message is fine, the second cannot be published
    channel.basic_publish.side_effect = [None, error]

    with pytest.raises(type(error)):
        replay_dead_letter_messages(channel, queue_manager)

    assert [call.kwargs["delivery_tag"] for call in channel.basic_ack.call_args_list] == [1]
    channel.basic_nack.assert_called_once_with(delivery_tag=2, requeue=True)
    assert channel.basic_get.call_count == 2  # the third message was never touched


def test_replay_moves_a_dead_lettered_message_back_to_the_main_queue(
    make_queue_config: Callable[..., QueueConfig],
) -> None:
    """With a real RabbitMQ: reject a message so the broker dead-letters it, then replay it."""
    queue_params = make_queue_config(batch_size=1, requeue_message=False).queue_params
    consumer = ConcreteQueueConsumer(queue_params)
    assert consumer.channel is not None
    channel = consumer.channel
    queue_manager = consumer.queue_manager
    message: dict[str, Any] = {"ht_id": "mdp.123", "ht_title": "Hello"}

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
        assert (
            channel.queue_declare(queue_manager.queue_name, passive=True).method.message_count == 0
        )

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
    channel, queue_manager = _fake_broker([_body("a")])
    channel.basic_publish.side_effect = pika.exceptions.ChannelClosed(320, "gone")
    channel.basic_nack.side_effect = pika.exceptions.ChannelWrongStateError("closed")

    with pytest.raises(pika.exceptions.ChannelClosed):
        replay_dead_letter_messages(channel, queue_manager)
