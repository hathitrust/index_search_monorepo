import inspect
import os
import sys

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.insert(0, current_dir)

# Full-text search config parameters
SOLR_URL = {
    "prod": "http://macc-ht-solr-lss-1.umdl.umich.edu:8081/solr/core-1x/query",
    "dev": "http://solr-lss-dev:8983/solr/core-x/query"
}

FULL_TEXT_SEARCH_SHARDS_X = ','.join([f"http://solr-sdr-search-{i}:8081/solr/core-{i}x" for i in range(1, 12)])
FULL_TEXT_SEARCH_SHARDS_Y = ','.join([f"http://solr-sdr-search-{i}:8081/solr/core-{i}y" for i in range(1, 12)])



QUERY_PARAMETER_CONFIG_FILE = os.path.join(current_dir, "config_files", "full_text_search", "config_query.yaml")

FACET_FILTERS_CONFIG_FILE = os.path.join(current_dir, "config_files", "full_text_search", "config_facet_filters.yaml")

DEFAULT_SOLR_PARAMS = {
    "rows": 500,
    "sort": "id asc",
    "fl": ",".join(["title", "author", "id", "shard", "score"]),
    "wt": "json"
}


def default_solr_params(env: str = "prod"):
    """
    Return the default solr parameters
    :param env:
    :return:
    """
    if env == "prod":
        add_shards(DEFAULT_SOLR_PARAMS)
    return DEFAULT_SOLR_PARAMS


def add_shards(params: dict):
    """
    Add shards to the params
    :param params:
    :return:
    """
    params.update({"shards": FULL_TEXT_SEARCH_SHARDS_X})
    return params
