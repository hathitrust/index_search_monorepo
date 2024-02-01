import pytest
from ht_full_text_search.ht_full_text_query import HTFullTextQuery
from ht_searcher.ht_searcher import HTSearcher
from ht_full_text_search.ht_full_text_searcher import HTFullTextSearcher

import os
import inspect
import sys

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

QUERY_PARAMETER_CONFIG_FILE = "/".join(
    [parentdir, "config_files/full_text_search/config_query.yaml"]
)
FACET_FILTERS_CONFIG_FILE = "/".join(
    [parentdir, "config_files/full_text_search/config_facet_filters.yaml"]
)

from ht_full_text_search.ht_full_text_query import HTFullTextQuery


@pytest.fixture
def ht_full_text_query_default_values():
    """
    Fixture that instantiates the HT Full Text Query class
    :return:
    """

    return HTFullTextQuery(config_query="all")


# General objects
@pytest.fixture
def ht_full_text_query():
    """
    Fixture that instantiates the HT Full Text Query class
    :return:
    """

    return HTFullTextQuery(
        config_query="all",
        config_query_path=QUERY_PARAMETER_CONFIG_FILE,
        user_id=None,
        config_facet_field="all",
        config_facet_field_path=FACET_FILTERS_CONFIG_FILE,
    )


@pytest.fixture
def ht_searcher_fixture(ht_search_query_fixture):
    """
    Fixture that instantiates the HTSearcher class
    :return:
    """

    return HTSearcher(
        engine_uri="http://localhost:8983/solr/#/core-x/",
        ht_search_query=ht_search_query_fixture,
        timeout=None,
        use_shards=False,
    )  # solr-lss-dev


# Specific objects (Full-text search)
@pytest.fixture
def ht_full_text_search_query_fixture():
    """
    Fixture that instantiates the HTFullTextQuery class
    :return:
    """

    return HTFullTextQuery(
        config_query="all",
        config_query_path=QUERY_PARAMETER_CONFIG_FILE,
        user_id=None,
        config_facet_field="all",
        config_facet_field_path=FACET_FILTERS_CONFIG_FILE,
    )


@pytest.fixture
def ht_full_text_search_fixture(ht_full_text_search_query_fixture):
    """
    Fixture that instantiates the HTFullTextQuery class
    :return:
    """

    query_string = "example query"
    return HTFullTextSearcher(
        engine_uri="http://localhost:8983/solr/#/core-x/",
        ht_search_query=ht_full_text_search_query_fixture,
        use_shards=False,
    )
