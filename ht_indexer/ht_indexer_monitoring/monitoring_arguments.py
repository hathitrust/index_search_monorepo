import os
import sys
import inspect

from ht_full_text_search.config_files import config_files_path
from ht_full_text_search.export_all_results import SolrExporter
from pathlib import Path


from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import get_solr_url

logger = get_ht_logger(name=__name__)

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

class MonitoringServiceArguments:
    def __init__(self, parser):
        parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))
        parser.add_argument("--query", help="Solr query",
                            default="*:*")

        parser.add_argument("--fl", help="Fields to return", default=["ht_id", "id"])
        parser.add_argument("--num_found", help="Total number of documents found", default=1000000)

        self.args = parser.parse_args()

        self.query = self.args.query
        self.output_fields = self.args.fl

        self.solr_host = get_solr_url()

        self.conf_query = "all"
        self.query_config_file_path = Path(config_files_path, 'catalog_search/config_query.yaml')

        self.solr_exporter = SolrExporter(self.solr_host, self.args.env,
                                     user=os.getenv("SOLR_USER"), password=os.getenv("SOLR_PASSWORD"))

