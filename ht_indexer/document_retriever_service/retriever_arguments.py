import os
import sys
import inspect
from ht_utils.ht_logger import get_ht_logger
from document_generator.document_generator import DocumentGenerator
from indexer_config import DOCUMENT_LOCAL_PATH
import ht_utils.ht_mysql
import ht_indexer_api.ht_indexer_api

logger = get_ht_logger(name=__name__)

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)


def get_solr_api():
    # Catalog Solr server
    try:
        solr_url = os.environ["SOLR_URL"]
    except KeyError:
        logger.error("Error: `SOLR_URL` environment variable required")
        sys.exit(1)

    return ht_indexer_api.ht_indexer_api.HTSolrAPI(url=solr_url)


def get_mysql_conn():
    # MySql connection
    try:
        mysql_host = os.environ["MYSQL_HOST"]
    except KeyError:
        logger.error("Error: `MYSQL_HOST` environment variable required")
        sys.exit(1)

    try:
        mysql_user = os.environ["MYSQL_USER"]
    except KeyError:
        logger.error("Error: `MYSQL_USER` environment variable required")
        sys.exit(1)

    try:
        mysql_pass = os.environ["MYSQL_PASS"]
    except KeyError:
        logger.error("Error: `MYSQL_PASS` environment variable required")
        sys.exit(1)

    ht_mysql = ht_utils.ht_mysql.HtMysql(
        host=mysql_host,
        user=mysql_user,
        password=mysql_pass,
        database=os.environ.get("MYSQL_DATABASE", "ht")
    )

    logger.info("Access by default to `ht` Mysql database")

    return ht_mysql


class RetrieverServiceArguments:
    def __init__(self, parser):
        parser.add_argument("--query", help="Query used to retrieve documents", default=None
                            )

        parser.add_argument("--document_repository",
                            help="Could be pairtree or local", default="local"
                            )

        # Path to the folder where the documents are stored. This parameter is useful for runing the script locally
        parser.add_argument("--document_local_path",
                            help="Path of the folder where the documents (.xml file to index) are stored.",
                            required=False,
                            default=None
                            )

        self.args = parser.parse_args()

        self.document_local_folder = "indexing_data"
        self.document_local_path = DOCUMENT_LOCAL_PATH
        self.document_repository = self.args.document_repository

        self.query = self.args.query

        # TODO: Add start and rows to a configuration file
        self.start = 0
        self.rows = 100

        self.document_generator = DocumentGenerator(get_mysql_conn())
        self.solr_api_catalog = get_solr_api()


class RetrieverServiceArgumentsByFile(RetrieverServiceArguments):
    def __init__(self, parser):
        parser.add_argument(
            "--list_ids_path",
            help="Path of the TXT files with the list of id to generate",
            required=False,
            default=None
        )

        super().__init__(parser)

        # args = self.parser.parse_args()
        self.list_ids_path = self.args.list_ids_path
