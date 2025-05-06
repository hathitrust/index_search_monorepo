import pytest
from pathlib import Path

from ht_full_text_search import config_files

from ht_full_text_search.ht_query.ht_query import HTSearchQuery
from ht_full_text_search.ht_full_text_searcher import HTFullTextSearcher
from ht_full_text_search.ht_searcher.ht_searcher import HTSearcher

QUERY_PARAMETER_CONFIG_FILE = Path(config_files.config_files_path, "full_text_search/config_query.yaml")
FACET_FILTERS_CONFIG_FILE = Path(config_files.config_files_path, "full_text_search/config_facet_filters.yaml")

@pytest.fixture
def ht_full_text_query_default_values():
    """
    Fixture that instantiates the HT Full Text Query class
    :return:
    """

    return HTSearchQuery(config_query="all")


# General objects
@pytest.fixture
def ht_full_text_query():
    """
    Fixture that instantiates the HT Full Text Query class
    :return:
    """

    return HTSearchQuery(
        config_query="all",
        config_query_path=str(QUERY_PARAMETER_CONFIG_FILE),
        user_id=None,
        config_facet_field="all",
        config_facet_field_path=str(FACET_FILTERS_CONFIG_FILE),
    )


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


# Specific objects (Full-text search)
@pytest.fixture
def ht_full_text_search_query_fixture():
    """
    Fixture that instantiates the HTFullTextQuery class
    :return:
    """

    return HTSearchQuery(
        config_query="all",
        config_query_path=str(QUERY_PARAMETER_CONFIG_FILE),
        user_id=None,
        config_facet_field="all",
        config_facet_field_path=str(FACET_FILTERS_CONFIG_FILE),
    )


@pytest.fixture
def ht_full_text_search_fixture(ht_full_text_search_query_fixture):
    """
    Fixture that instantiates the HTFullTextQuery class
    :return:
    """

    return HTFullTextSearcher(
        solr_url="http://solr-lss-dev:8983/solr/#/core-x/",
        ht_search_query=ht_full_text_search_query_fixture
    )
