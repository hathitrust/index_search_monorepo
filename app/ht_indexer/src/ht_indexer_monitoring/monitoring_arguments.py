import argparse
import os
from pathlib import Path

from ht_search.config_files import config_files_path
from ht_search.export_all_results import SolrExporter
from ht_utils.ht_env_config import HtEnvConfig
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class MonitoringServiceArguments:
    def __init__(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))
        parser.add_argument("--query", help="Solr query", default="*:*")

        parser.add_argument("--fl", help="Fields to return", default=["ht_id", "id"])
        parser.add_argument("--num_found", help="Total number of documents found", default=1000000)

        self.args = parser.parse_args()

        self.query = self.args.query
        self.output_fields = self.args.fl

        self.solr_url = HtEnvConfig().catalog_solr_ro_url

        self.conf_query = "all"
        # importlib.resources.files() is typed as Traversable, which typeshed doesn't declare
        # as PathLike -- but for this package (a regular installed directory, not a zip) it is.
        self.query_config_file_path = Path(
            config_files_path,  # type: ignore[arg-type]
            "catalog_search/config_query.yaml",
        )

        self.solr_exporter = SolrExporter(self.solr_url, self.args.env)
