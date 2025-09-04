import os
import sys

from . import indexer_config_file_path
from config import config_queue_file_path
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_queue_service.queue_config import QueueConfig
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import get_general_error_message

logger = get_ht_logger(name=__name__)


class IndexerServiceArguments:

    def __init__(self, parser):
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
            default=None
        )

        parser.add_argument(
            "--batch_size",
            help="Integer that represents the number of documents to process in a batch."
        )

        self.args = parser.parse_args()

        solr_user = os.getenv("SOLR_USER")
        solr_password = os.getenv("SOLR_PASSWORD")

        self.solr_api_full_text = HTSolrAPI(url=self.args.solr_indexing_api,
                                            user=solr_user,
                                            password=solr_password)

        self.document_local_path = self.args.document_local_path

        try:
            # Using queue or local machine
            ############### QUEUE CONFIGURATION ####################
            # Build resource file paths using Traversable's '/' operator
            global_config = config_queue_file_path / 'global_config.yml'
            app_config = indexer_config_file_path / 'indexer_config.yml'
            # Validate that the files actually exist
            if not global_config.is_file():
                logger.error(f"Queue config file {global_config} does not exist")
                sys.exit(1)
            if not app_config.is_file():
                logger.error(f"Queue config file {app_config} does not exist")
                sys.exit(1)
            self.queue_config = QueueConfig(global_config, app_config, config_key="queue")

        except KeyError as e:
            logger.error(f"Environment variables required: "
                         f"{get_general_error_message('DocumentIndexerService', e)}")

            sys.exit(1)



