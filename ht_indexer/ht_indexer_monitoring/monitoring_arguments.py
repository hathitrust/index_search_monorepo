import os
import sys
import inspect

from ht_full_text_search.config_files import config_files_path
from ht_full_text_search.config_search import CATALOG_SOLR_URL
from ht_full_text_search.export_all_results import SolrExporter
from pathlib import Path


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


class MonitoringServiceArguments:
    def __init__(self, parser):
        parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))
        parser.add_argument("--query", help="Solr query",
                            default="*:*")

        parser.add_argument("--query_field",
                            help="Could be item or record. If item, the query contains the ht_id of the item",
                            default="ht_id"
                            )
        parser.add_argument("--fl", help="Fields to return", default=["ht_id", "id"])
        parser.add_argument("--num_found", help="Total number of documents found", default=1000000)
        parser.add_argument("--solr_host", help="Solr url", default=None)
        parser.add_argument("--collection_name", help="Name of the collection", default="catalog")

        self.args = parser.parse_args()

        self.query = self.args.query
        self.query_field = self.args.query_field
        self.output_fields = self.args.fl

        # Query Catalog Solr server
        if self.args.solr_host:
            self.solr_host = self.args.solr_host
        else:
            self.solr_host = CATALOG_SOLR_URL[self.args.env]

        self.conf_query = "all"
        self.query_config_file_path = Path(config_files_path, 'catalog_search/config_query.yaml')

        self.solr_exporter = SolrExporter(f"{self.solr_host}/solr/{self.args.collection_name}", self.args.env,
                                     user=os.getenv("SOLR_USER"), password=os.getenv("SOLR_PASSWORD"))

