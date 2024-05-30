import os
import sys
import inspect

import ht_utils.ht_utils
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)


def comma_separated_list(arg):
    return arg.split(",")


def get_solr_api():
    # Catalog Solr server
    try:
        solr_url = os.getenv("SOLR_URL")
    except KeyError:
        logger.error("Error: `SOLR_URL` environment variable required")
        sys.exit(1)

    return solr_url


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
            self.dead_letter_queue = True
        except KeyError as e:
            logger.error(f"Environment variables required: "
                         f"{ht_utils.ht_utils.get_general_error_message('DocumentGeneratorService', e)}")

            sys.exit(1)
        self.args = parser.parse_args()

        self.list_documents = self.args.list_documents
        self.query_field = self.args.query_field

        # TODO: Add start and rows to a configuration file
        self.start = 0
        self.rows = 100

        self.solr_api_url = get_solr_api()


class RetrieverServiceByFileArguments(RetrieverServiceArguments):

    def __init__(self, parser):
        parser.add_argument("--input_document_file", help="TXT file containing the list of items to process",
                            default='')

        super().__init__(parser)

        self.input_documents_file = self.args.input_document_file
        if not os.path.isfile(self.input_documents_file):
            logger.error(f"File {self.input_documents_file} does not exist")
            sys.exit(1)
