import inspect
import json
import os
import sys
import time
from argparse import ArgumentParser
from statistics import mean, median

import requests
from ht_search.config_search import CATALOG_SOLR_URL, FULL_TEXT_SOLR_URL
from ht_search.export_all_results import SolrExporter
from ht_utils.ht_logger import get_ht_logger
from requests.auth import HTTPBasicAuth

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

logger = get_ht_logger(name=__name__)

def send_solr_query(solr_base_url: str, query: dict = None,
                    user: str = None, password: str = None, response_times: list = None,
                    error_count: int = 0, total_queries: int = 0) -> None:
    """
    Send a query to Solr and measure the response time.
    :param total_queries:
    :param error_count:
    :param response_times:
    :param password:
    :param user:
    :param query:
    :param solr_base_url:
    :return:
    """

    try:
        # Construct Solr query URL
        url = f"{solr_base_url}/select"

        # Record start time
        start_time = time.time()

        auth = HTTPBasicAuth(user, password) if user and password else None

        # Send query request
        response = requests.get(url, params=query, timeout=10, auth=auth)
        output = json.loads(response.content)

        for result in output['response']['docs']:
            logger.info(result)

        # Record end time
        end_time = time.time()

        # Calculate response time
        response_time = end_time - start_time
        response_times.append(response_time)

        # Check for errors
        if response.status_code != 200:
            logger.info(f"Error: Received status code {response.status_code}")
            error_count += 1
        else:
            logger.info(f"Query successful. Response time: {response_time:.3f} seconds")
    except Exception as e:
        logger.error(f"Error: {e}")
        error_count += 1
    finally:
        total_queries += 1

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
    parser.add_argument("--solr_host", help="Solr url", default=None)
    parser.add_argument("--collection_name", help="Name of the collection", default=None)
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
    solr_host = FULL_TEXT_SOLR_URL[args.env]
    config_files = 'full_text_search'
    conf_query = "ocr"

    # Overwrite default parameter for Catalog search
    if args.cluster_name == "catalog":
        solr_host = CATALOG_SOLR_URL[args.env]
        config_files = 'catalog_search'
        conf_query = "titleonly"

    if args.solr_host:
        solr_base_url = f"{args.solr_host}/solr/{args.collection_name}"
    else:
        solr_base_url = f"{solr_host}/solr/{args.collection_name}"


    while time.time() - start_time < test_duration:
        # TODO: Generate a random Solr query using different kind of queries and parameters
        # Query by id,
        # Query that involves different shards by title, query by author, query by date, query by source
        # Faceted search

        query_config_file_path = os.path.join(os.path.abspath(os.path.join(parent)),
                                              'config_files', config_files, 'config_query.yaml')

        query = "health"
        solr_exporter = SolrExporter(solr_base_url, args.env,
                                     user=os.getenv("SOLR_USER"), password=os.getenv("SOLR_PASSWORD"))
        # '"good"'
        for x in solr_exporter.run_cursor(query, query_config_file_path, conf_query=conf_query):
            logger.info(x)

        time.sleep(interval)

    # Only for Catalog queries
    print_metrics(response_times, error_count, total_queries)



if __name__ == "__main__":
    main()