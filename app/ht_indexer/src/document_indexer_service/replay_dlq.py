"""Move messages from the indexer's dead-letter queue back to the indexer queue.

Run it by hand once the cause of the failures is fixed (Solr back, document corrected):

    python -m document_indexer_service.replay_dlq --dry-run     # look first
    python -m document_indexer_service.replay_dlq --max 100     # replay up to 100 messages
    python -m document_indexer_service.replay_dlq               # replay everything

The queue name comes from indexer_config.yml. The RabbitMQ host, port, username and password come
from the RABBITMQ_INDEXER_RW_* environment variables (see HtEnvConfig), like for the indexer service.
"""

import argparse
import sys

from config import config_queue_file_path
from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.dead_letter_replay import replay_dead_letter_messages
from ht_queue_service.queue_config import QueueConfig
from ht_queue_service.queue_manager import QueueManager
from ht_utils.ht_logger import get_ht_logger
from pika.exceptions import AMQPError

from . import indexer_config_file_path

logger = get_ht_logger(name=__name__)


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Move messages from the indexer's dead-letter queue back to the indexer queue."
    )
    parser.add_argument(
        "--max", type=_positive_int, default=None, help="Replay at most this many messages."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which messages would be replayed, without moving anything.",
    )
    args = parser.parse_args()

    # importlib.resources.files() is typed as Traversable, which typeshed doesn't declare as
    # PathLike -- but for these packages (regular installed directories, not zips) they are.
    queue_params = QueueConfig(
        config_queue_file_path / "global_config.yml",  # type: ignore[arg-type]
        indexer_config_file_path / "indexer_config.yml",  # type: ignore[arg-type]
        config_key="queue",
    ).get_params()

    channel_creator = ChannelCreator(
        queue_params.user, queue_params.password, queue_params.host, queue_params.heartbeat
    )
    channel = channel_creator.get_channel()
    if channel is None:
        logger.error("Unable to establish a RabbitMQ channel")
        sys.exit(1)

    try:
        replay_dead_letter_messages(
            channel, QueueManager(queue_params), max_messages=args.max, dry_run=args.dry_run
        )
    except AMQPError as error:
        # Details were logged where it failed; the message that failed is still in the DLQ
        logger.error(f"Replay stopped: {error}")
        sys.exit(1)
    finally:
        if channel.is_open:
            channel.close()
        if channel_creator.connection.queue_connection is not None:
            channel_creator.connection.queue_connection.close()


if __name__ == "__main__":
    main()
