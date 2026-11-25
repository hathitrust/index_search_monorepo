import os
import time
from argparse import ArgumentParser
from statistics import mean, median

from ht_search.export_all_results import SolrExporter
from ht_utils.ht_env_config import ht_env_config
from ht_utils.ht_logger import get_ht_logger

current = os.path.dirname(os.path.abspath(__file__))
parent = os.path.dirname(current)

logger = get_ht_logger(name=__name__)


def print_metrics(response_times: list, error_count: int, total_queries: int) -> None:
    logger.info("\n=== Solr Query Performance Metrics ===")
    logger.info(f"Total Queries: {total_queries}")
    logger.info(f"Errors: {error_count}")
    if response_times:
        logger.info(f"Average Response Time: {mean(response_times):.3f} seconds")
        logger.info(f"Median Response Time: {median(response_times):.3f} seconds")
        logger.info(f"Fastest Query Time: {min(response_times):.3f} seconds")
        logger.info(f"Slowest Query Time: {max(response_times):.3f} seconds")
    else:
        logger.info("No successful queries recorded.")
    logger.info("======================================\n")


def main():

    parser = ArgumentParser()
    parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))
    parser.add_argument("--cluster_name", help="It can be catalog or fulltext", required=True)

    args = parser.parse_args()

    # Set the experiment parameters
    interval = 1  # seconds
    test_duration = 60  # seconds
    response_times = []
    error_count = 0
    total_queries = 0

    logger.info("Starting Solr Query Performance Test...")
    start_time = time.time()

    # Default parameters are for full-text search
    solr_params = ht_env_config.solr_full_text_ro
    config_files = "full_text_search"
    conf_query = "ocr"

    # Overwrite default parameter for Catalog search
    if args.cluster_name == "catalog":
        solr_params = ht_env_config.solr_catalog_ro
        config_files = "catalog_search"
        conf_query = "titleonly"

    while time.time() - start_time < test_duration:
        # TODO: Generate a random Solr query using different kind of queries and parameters
        # Query by id,
        # Query that involves different shards by title, query by author, query by date, query by source
        # Faceted search

        query_config_file_path = os.path.join(
            os.path.abspath(os.path.join(parent)), "config_files", config_files, "config_query.yaml"
        )

        query = "health"
        solr_exporter = SolrExporter(solr_params, args.env)
        # '"good"'
        for x in solr_exporter.run_query_term_cursor(
            query, query_config_file_path, conf_query=conf_query
        ):
            logger.info(x)

        time.sleep(interval)

    # Only for Catalog queries
    print_metrics(response_times, error_count, total_queries)


if __name__ == "__main__":
    main()
