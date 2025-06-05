import pytest
from pathlib import Path

from ht_search import config_files
from ht_search.ht_query.ht_query import HTSearchQuery
from ht_search.ht_searcher.ht_searcher import HTSearcher

QUERY_PARAMETER_CONFIG_FILE = Path(config_files.config_files_path, "full_text_search/config_query.yaml")
FACET_FILTERS_CONFIG_FILE = Path(config_files.config_files_path, "full_text_search/config_facet_filters.yaml")


@pytest.fixture
def ht_searcher_fixture(ht_search_query_fixture):
    """
    Fixture that instantiates the HTSearcher class
    :return:
    """

    return HTSearcher(
        solr_url="http://solr-lss-dev:8983/solr/#/core-x/",
        ht_search_query=ht_search_query_fixture,
        environment="dev"
    )


