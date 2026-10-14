import dataclasses
import json

import pika
from ht_utils.ht_logger import get_ht_logger
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPError, NackError, UnroutableError

from ht_queue_service.queue_manager import QueueManager

logger = get_ht_logger(name=__name__)

DELIVERY_MODE_PERSISTENT = 2


@dataclasses.dataclass(frozen=True)
class ReplaySummary:
    in_dead_letter_queue: int  # Messages in the dead-letter queue when the replay started
    replayed: int  # Messages moved back to the main queue (always 0 for a dry run)
    inspected: int  # Messages looked at (a dry run only looks)


def _ht_id(body: bytes) -> str | None:
    try:
        ht_id = json.loads(body).get("ht_id")
    except ValueError, AttributeError:
        return None
    return None if ht_id is None else str(ht_id)


def replay_dead_letter_messages(
    channel: BlockingChannel,
    queue_manager: QueueManager,
    max_messages: int | None = None,
    dry_run: bool = False,
) -> ReplaySummary:
    """Move messages from the dead-letter queue back to the main queue.

    Each message is published to the main exchange first, and acknowledged in the dead-letter
    queue only after RabbitMQ confirms the publish. If anything fails in between, the message
    stays in the dead-letter queue. A crash between the publish and the ack can leave a duplicate,
    which is harmless for indexing: Solr overwrites a document with the same id.

    Only as many messages as were in the dead-letter queue at the start are looked at, so a message
    that fails again and is dead-lettered again cannot keep the replay running forever.

    :param channel: An open RabbitMQ channel
    :param queue_manager: Gives the names of the main queue, its exchange and the dead-letter queue
    :param max_messages: Replay at most this many messages (None means all of them)
    :param dry_run: Only report which messages would be replayed; leave the dead-letter queue as is
    :raises pika.exceptions.ChannelClosedByBroker: If the dead-letter queue does not exist
    :raises pika.exceptions.AMQPError: If publishing a message fails (that message is left in place)
    """
    dead_letter_queue = queue_manager.dead_letter_queue_name
    # passive=True: only look, never create the queue
    status = channel.queue_declare(queue=dead_letter_queue, passive=True)
    in_dead_letter_queue = status.method.message_count or 0
    limit = (
        in_dead_letter_queue if max_messages is None else min(in_dead_letter_queue, max_messages)
    )

    if not dry_run:
        # Make basic_publish wait for the broker's confirmation (and raise if it refuses)
        channel.confirm_delivery()

    logger.info(
        f"event=dlq_replay_started queue={dead_letter_queue} in_dead_letter_queue="
        f"{in_dead_letter_queue} limit={limit} dry_run={dry_run}"
    )

    inspected = 0
    replayed = 0
    last_tag: int | None = None
    for _ in range(limit):
        method_frame, _, body = channel.basic_get(queue=dead_letter_queue, auto_ack=False)
        # GetOk always carries a delivery_tag and body; pika-stubs types both Optional.
        if method_frame is None or method_frame.delivery_tag is None or body is None:
            break  # Someone else emptied the queue
        delivery_tag = method_frame.delivery_tag
        inspected += 1
        last_tag = delivery_tag
        # At runtime the body is bytes; pika-stubs types it as str.
        payload = body.encode() if isinstance(body, str) else body
        ht_id = _ht_id(payload)

        if dry_run:
            logger.info(f"event=dlq_replay_would_replay ht_id={ht_id}")
            continue

        try:
            channel.basic_publish(
                exchange=queue_manager.main_exchange_name,
                routing_key=queue_manager.queue_name,
                body=payload,
                properties=pika.BasicProperties(
                    delivery_mode=DELIVERY_MODE_PERSISTENT, content_type="application/json"
                ),
                mandatory=True,  # Raise UnroutableError instead of dropping it silently
            )
        except (UnroutableError, NackError, AMQPError) as error:
            # Leave this message in the dead-letter queue and stop
            channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
            logger.error(
                f"event=dlq_replay_failed ht_id={ht_id} replayed={replayed} error={str(error)!r}"
            )
            raise
        channel.basic_ack(delivery_tag=delivery_tag)
        replayed += 1
        logger.info(f"event=dlq_replay_message ht_id={ht_id}")

    if dry_run and last_tag is not None:
        # Hand every message we only looked at back to the dead-letter queue
        channel.basic_nack(delivery_tag=last_tag, multiple=True, requeue=True)

    logger.info(
        f"event=dlq_replay_finished in_dead_letter_queue={in_dead_letter_queue} "
        f"inspected={inspected} replayed={replayed} dry_run={dry_run}"
    )
    return ReplaySummary(
        in_dead_letter_queue=in_dead_letter_queue, replayed=replayed, inspected=inspected
    )
