import argparse
import sys

from ht_indexer_api.ht_indexer_api import (
    DEFAULT_READ_TIMEOUT_SECONDS,
    HTSolrAPI,
    positive_seconds,
)
from ht_queue_service.queue_settings import QueueSettings
from ht_utils.ht_env_config import HtEnvConfig
from ht_utils.ht_logger import get_ht_logger
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from . import indexer_config_file_path

logger = get_ht_logger(name=__name__)

# Higher than the HTSolrAPI default (10s), which the search and retriever code still use: while
# uploading a batch, Solr may stop reading for longer than that and the upload is cut.
INDEXER_CONNECT_TIMEOUT_SECONDS = 60.0


class IndexerQueueSettings(QueueSettings):
    model_config = SettingsConfigDict(
        env_prefix="RABBITMQ_INDEXER_",
        yaml_file=indexer_config_file_path / "indexer_config.yml",
        yaml_config_section="queue",
    )


class IndexerServiceArguments:
    def __init__(self, parser: argparse.ArgumentParser) -> None:
        # Path to the folder where the documents are stored. This parameter is useful for running the script locally
        parser.add_argument(
            "--document_local_path",
            help="Path of the folder where the documents are stored.",
            required=False,
            default=None,
        )

        parser.add_argument(
            "--batch_size",
            type=int,
            default=None,
            help="Number of documents to process in a batch (1 to 65535). "
            "Overrides batch_size in indexer_config.yml; without it, the config value is used.",
        )

        parser.add_argument(
            "--solr_timeout",
            type=positive_seconds,
            default=DEFAULT_READ_TIMEOUT_SECONDS,
            help="Seconds to wait for Solr to send data before a request fails (default: "
            f"{DEFAULT_READ_TIMEOUT_SECONDS:g}). It is the longest silence allowed between bytes "
            "from Solr, not a limit on the whole request. A timeout is treated as a temporary "
            "failure: the messages stay on the queue.",
        )

        parser.add_argument(
            "--solr_connect_timeout",
            type=positive_seconds,
            default=INDEXER_CONNECT_TIMEOUT_SECONDS,
            help="Seconds to wait for Solr to accept the connection (default: "
            f"{INDEXER_CONNECT_TIMEOUT_SECONDS:g}). The HTTP client also applies it while the "
            "request body is being sent, so it is the longest an upload may stall before the "
            "request fails with 'Connection aborted ... timed out'. A timeout is treated as a "
            "temporary failure: the messages stay on the queue.",
        )

        self.args = parser.parse_args()

        env_config = HtEnvConfig()

        self.solr_api_full_text = HTSolrAPI(
            env_config.solr_full_text_rw,
            read_timeout=self.args.solr_timeout,
            connect_timeout=self.args.solr_connect_timeout,
        )

        self.document_local_path = self.args.document_local_path

        overrides = {}

        if self.args.batch_size is not None:
            overrides["batch_size"] = self.args.batch_size

        try:
            self.queue_settings = IndexerQueueSettings(**overrides)
        except ValidationError as e:
            logger.error(f"Invalid queue configuration: {e}")
            sys.exit(1)
