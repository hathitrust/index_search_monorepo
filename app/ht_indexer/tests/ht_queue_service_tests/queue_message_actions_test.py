from unittest.mock import MagicMock

import pytest
from ht_queue_service.queue_multiple_consumer import QueueMultipleConsumer


class _Consumer(QueueMultipleConsumer):
    """Minimal concrete consumer. __init__ is never run (it connects to RabbitMQ), so only
    the ack/nack/reject helpers, which don't touch instance state other than requeue_message,
    can be exercised.
    """

    def process_batch(self, batch: list[object], delivery_tag: list[int]) -> bool:
        return True


def _consumer(requeue_message: bool) -> _Consumer:
    consumer = _Consumer.__new__(_Consumer)
    consumer.requeue_message = requeue_message
    return consumer


@pytest.mark.parametrize("requeue_message", [True, False])
def test_retry_message_requeues_whatever_the_flag_says(requeue_message: bool) -> None:
    channel = MagicMock()

    _consumer(requeue_message).retry_message(channel, 7)

    channel.basic_nack.assert_called_once_with(delivery_tag=7, requeue=True)
    channel.basic_reject.assert_not_called()


@pytest.mark.parametrize("requeue_message", [True, False])
def test_dead_letter_message_never_requeues_whatever_the_flag_says(requeue_message: bool) -> None:
    channel = MagicMock()

    _consumer(requeue_message).dead_letter_message(channel, 7)

    channel.basic_reject.assert_called_once_with(delivery_tag=7, requeue=False)
    channel.basic_nack.assert_not_called()


def test_reject_message_still_follows_the_requeue_flag() -> None:
    """reject_message is used by the retriever and generator services and must not change."""
    channel = MagicMock()

    _consumer(True).reject_message(channel, 7)

    channel.basic_reject.assert_called_once_with(delivery_tag=7, requeue=True)
