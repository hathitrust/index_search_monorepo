import os
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_queue_service.queue_consumer import QueueConsumer


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

        self.args = parser.parse_args()

        self.solr_api_full_text = HTSolrAPI(url=self.args.solr_indexing_api)

        self.document_local_path = self.args.document_local_path

        # Using queue
        self.queue_consumer = QueueConsumer(os.environ["QUEUE_USER"],
                                            os.environ["QUEUE_PASS"],
                                            os.environ["QUEUE_HOST"],
                                            os.environ["QUEUE_NAME"])
