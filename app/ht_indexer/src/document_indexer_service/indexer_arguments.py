import os

from catalog_metadata.ht_indexer_config import (
    indexer_batch_size,
    indexer_queue_name,
    indexer_requeue_message,
)
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_utils.ht_logger import get_ht_logger

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

        self.queue_parameters = {
            "queue_user": os.getenv("QUEUE_USER"),
            "queue_pass": os.getenv("QUEUE_PASS"),
            "queue_host": os.getenv("QUEUE_HOST"),
            "queue_name": os.getenv("QUEUE_NAME") if os.getenv("QUEUE_NAME") else indexer_queue_name,
            "requeue_message": indexer_requeue_message,
            "batch_size": int(self.args.batch_size) if self.args.batch_size else indexer_batch_size,
            "shutdown_on_empty_queue": False,  # The indexer process is a long-running service
                # that does not stop when the queue is empty.
        }

