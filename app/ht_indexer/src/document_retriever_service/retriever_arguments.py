import inspect
import os
import sys

from document_generator.ht_mysql import get_mysql_conn
from ht_indexer_monitoring.ht_indexer_tracktable import PROCESSING_STATUS_TABLE_NAME
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import comma_separated_list, get_general_error_message, get_solr_url

logger = get_ht_logger(name=__name__)

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

SOLR_ROW_START = 0
SOLR_TOTAL_ROWS = 200
TOTAL_MYSQL_ROWS = 24000


class RetrieverServiceArguments:
    def __init__(self, parser):
        parser.add_argument("--list_documents", help="List of items to process",
                            default=[],
                            type=comma_separated_list)

        parser.add_argument("--query_field",
                            help="Could be item or record. If item, the query contains the ht_id of the item",
                            default="ht_id"
                            )

        try:
            # Using queue or local machine
            self.queue_name = os.environ["QUEUE_NAME"]
            self.queue_host = os.environ["QUEUE_HOST"]
            self.queue_user = os.environ["QUEUE_USER"]
            self.queue_password = os.environ["QUEUE_PASS"]
        except KeyError as e:
            logger.error(f"Environment variables required: "
                         f"{get_general_error_message('DocumentGeneratorService', e)}")

            sys.exit(1)
        self.args = parser.parse_args()

        # MySql connection
        self.db_conn = get_mysql_conn(pool_size=1)

        self.list_documents = self.args.list_documents
        self.query_field = self.args.query_field

        # Retriever 24k items from the database
        self.retriever_query = f"SELECT ht_id, record_id FROM {PROCESSING_STATUS_TABLE_NAME} WHERE retriever_status = 'pending' LIMIT {TOTAL_MYSQL_ROWS}"

        # TODO Remove the line below once SolrExporter been updated self.solr_url = f"{solr_url}/query"

        self.solr_host = get_solr_url()
        self.solr_user=os.getenv("SOLR_USER")
        self.solr_password=os.getenv("SOLR_PASSWORD")

        self.solr_retriever_query_params = {
        'q': '*:*',
        'rows': SOLR_TOTAL_ROWS,
        'wt': 'json'
    }


class RetrieverServiceByFileArguments(RetrieverServiceArguments):

    def __init__(self, parser):
        parser.add_argument("--input_document_file", help="TXT file containing the list of items to process",
                            default='')

        super().__init__(parser)

        self.input_documents_file = self.args.input_document_file
        if not os.path.isfile(self.input_documents_file):
            logger.error(f"File {self.input_documents_file} does not exist")
            sys.exit(1)
