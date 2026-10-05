import argparse
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

class MonitoringServiceArguments:
    def __init__(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--query", help="Solr query", default="*:*")
        parser.add_argument("--num_found", help="Total number of documents found", default=1000000)

        self.args = parser.parse_args()
        self.query = self.args.query
