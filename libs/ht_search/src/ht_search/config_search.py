import copy
import os
from typing import Any

current_dir = os.path.dirname(os.path.abspath(__file__))

# Full-text search config parameters
FULL_TEXT_SOLR_RO_URL = os.environ["FULL_TEXT_SOLR_RO_URL"]
CATALOG_SOLR_RO_URL = os.environ["CATALOG_SOLR_RO_URL"]

# only needed for old (pre-solr-cloud) production
FULL_TEXT_SEARCH_SHARDS_X = ",".join(
    [f"http://solr-sdr-search-{i}:8081/solr/core-{i}x" for i in range(1, 12)]
)

QUERY_PARAMETER_CONFIG_FILE = os.path.join(
    current_dir, "config_files", "full_text_search", "config_query.yaml"
)
FACET_FILTERS_CONFIG_FILE = os.path.join(
    current_dir, "config_files", "full_text_search", "config_facet_filters.yaml"
)

DEFAULT_SOLR_PARAMS = {
    "rows": 500,
    "sort": "id asc",
    "fl": ",".join(["title", "author", "id", "shard", "score"]),
    "wt": "json",
}


def default_solr_params(env: str = "prod") -> dict[str, Any]:
    # TODO: Add shards is only for prod environment and full-text search, then I have to change this function to
    # ensure we have access to Catalog in prod environment.
    """
    Return the default solr parameters
    :param env:
    :return:
    """
    params = copy.deepcopy(DEFAULT_SOLR_PARAMS)
    if env == "prod":
        add_shards(params)
    return params


def add_shards(params: dict[str, Any]) -> dict[str, Any]:
    """
    Add shards to the params
    :param params:
    :return:
    """
    params.update({"shards": FULL_TEXT_SEARCH_SHARDS_X})
    return params
