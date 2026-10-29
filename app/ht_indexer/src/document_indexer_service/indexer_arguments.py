import argparse
import sys

from config import config_queue_file_path
from ht_indexer_api.ht_indexer_api import (
    DEFAULT_READ_TIMEOUT_SECONDS,
    HTSolrAPI,
    validate_timeout_seconds,
)
from ht_queue_service.queue_config import QueueConfig
from ht_utils.ht_env_config import HtEnvConfig
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import get_general_error_message

from . import indexer_config_file_path

logger = get_ht_logger(name=__name__)


def _positive_seconds(value: str) -> float:
    try:
        return validate_timeout_seconds("--solr_timeout", float(value))
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


class IndexerServiceArguments:
    def __init__(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--solr_indexing_api",
            help="",
            required=True,
            default="http://solr-lss-dev:8983/solr/#/core-x/",
        )

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
            type=_positive_seconds,
            default=DEFAULT_READ_TIMEOUT_SECONDS,
            help="Seconds to wait for Solr to send data before a request fails (default: "
            f"{DEFAULT_READ_TIMEOUT_SECONDS:g}). It is the longest silence allowed between bytes "
            "from Solr, not a limit on the whole request. A timeout is treated as a temporary "
            "failure: the messages stay on the queue.",
        )

        self.args = parser.parse_args()

        env_config = HtEnvConfig()
        solr_user = env_config.solr_user
        solr_password = env_config.solr_password

        self.solr_api_full_text = HTSolrAPI(
            url=self.args.solr_indexing_api,
            user=solr_user,
            password=solr_password,
            read_timeout=self.args.solr_timeout,
        )

        self.document_local_path = self.args.document_local_path

        try:
            # Using queue or local machine
            ############### QUEUE CONFIGURATION ####################
            # Build resource file paths using Traversable's '/' operator
            global_config = config_queue_file_path / "global_config.yml"
            app_config = indexer_config_file_path / "indexer_config.yml"
            # Validate that the files actually exist
            if not global_config.is_file():
                logger.error(f"Queue config file {global_config} does not exist")
                sys.exit(1)
            if not app_config.is_file():
                logger.error(f"Queue config file {app_config} does not exist")
                sys.exit(1)
            # importlib.resources.files() is typed as Traversable, which typeshed doesn't
            # declare as PathLike -- but for these packages (regular installed directories,
            # not zips) they are.
            self.queue_config = QueueConfig(
                global_config,  # type: ignore[arg-type]
                app_config,  # type: ignore[arg-type]
                config_key="queue",
                batch_size=self.args.batch_size,
            )

        except ValueError as e:
            # For example, a --batch_size outside the allowed range
            logger.error(f"Invalid queue configuration: {e}")
            sys.exit(1)

        except KeyError as e:
            logger.error(
                f"Environment variables required: "
                f"{get_general_error_message('DocumentIndexerService', e)}"
            )

            sys.exit(1)
