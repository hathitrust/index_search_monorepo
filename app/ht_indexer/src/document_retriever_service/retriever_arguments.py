import argparse
import multiprocessing
import os
import sys
import tempfile

from config import config_queue_file_path
from ht_indexer_api.ht_indexer_api import DEFAULT_READ_TIMEOUT_SECONDS, positive_seconds
from ht_queue_service.queue_config import QueueConfig
from ht_utils.ht_env_config import HtEnvConfig
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import comma_separated_list, get_general_error_message

from . import retriever_config_file_path

logger = get_ht_logger(name=__name__)

SOLR_ROW_START = 0
SOLR_TOTAL_ROWS = 200
MAX_WORKERS = 20


class RetrieverServiceArguments:
    # Add argv parameter to allow custom args and avoid mocking sys.argv in tests
    def __init__(self, parser: argparse.ArgumentParser, argv: list[str] | None = None) -> None:
        parser.add_argument(
            "--list_documents",
            help="List of items to process",
            default=[],
            type=comma_separated_list,
        )

        parser.add_argument(
            "--query_field",
            help="Could be item or record. If item, the query contains the ht_id of the item",
            choices=["item", "record"],
            default="item",
        )
        parser.add_argument(
            "--parallelize",
            help="Retrieve documents in parallel using multiple threads",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "--solr_timeout",
            type=positive_seconds,
            default=DEFAULT_READ_TIMEOUT_SECONDS,
            help="Seconds to wait for the Catalog Solr to send data before a request fails "
            f"(default: {DEFAULT_READ_TIMEOUT_SECONDS:g}). It is the longest silence allowed "
            "between bytes from Solr, not a limit on the whole request.",
        )

        try:
            # Using queue or local machine
            ############### QUEUE CONFIGURATION ####################
            # Build resource file paths using Traversable's '/' operator
            global_config = config_queue_file_path / "global_config.yml"
            app_config = retriever_config_file_path / "retriever_config.yml"
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
            )
            ########################################################

        except KeyError as e:
            logger.error(
                f"Environment variables required: "
                f"{get_general_error_message('DocumentIndexerService', e)}"
            )

            sys.exit(1)
        self.args = parser.parse_args(argv)

        self.parallelize = self.args.parallelize
        self.max_workers = 1
        if self.parallelize:
            self.max_workers = min(multiprocessing.cpu_count() * 2, MAX_WORKERS)

        self.list_documents = self.args.list_documents
        self.query_field = self.args.query_field
        self.solr_timeout = self.args.solr_timeout

        env_config = HtEnvConfig()
        self.solr_host = env_config.catalog_solr_ro_url
        # The catalog Solr has its own optional credentials; the full-text SOLR_USER/SOLR_PASSWORD don't apply here
        self.solr_user = env_config.solr_catalog_ro_username
        self.solr_password = env_config.solr_catalog_ro_password

        self.solr_retriever_query_params = {"q": "*:*", "rows": SOLR_TOTAL_ROWS, "wt": "json"}


class RetrieverServiceByFileArguments(RetrieverServiceArguments):
    def __init__(self, parser: argparse.ArgumentParser, argv: list[str] | None = None) -> None:
        parser.add_argument(
            "--input_document_file",
            help="TXT file containing the list of items to process",
            default="",
        )
        parser.add_argument(
            "--status_file",
            help="Path to the file used to track which document IDs have been processed.",
            default=os.path.join(tempfile.gettempdir(), "document_retriever_status.txt"),
        )

        super().__init__(parser, argv)

        self.input_documents_file = self.args.input_document_file
        if not os.path.isfile(self.input_documents_file):
            logger.error(f"File {self.input_documents_file} does not exist")
            sys.exit(1)
        self.status_file: str = self.args.status_file
