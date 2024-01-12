"""
import pytest
from ht_full_text_search.ht_full_text_query import HTFullTextQuery
from ht_searcher.ht_searcher import HTSearcher


@pytest.fixture(scope="module")
def ht_full_text_query_fixture():
    '''
    Fixture that instantiates the HT Full Text Query class
    :return:
    '''

    query_string = "example query"
    internal = [[1, 234, 4, 456, 563456, 43563, 3456345634]]
    return HTFullTextQuery(query_string, internal)


@pytest.fixture(scope="module", autouse=True)
def ht_searcher_fixture():
    '''
    Fixture that instantiates the HTSearcher class
    :return:
    '''

    return HTSearcher(engine_uri="http://localhost:8983/solr/#/core-x/", timeout=None) #solr-lss-dev

"""