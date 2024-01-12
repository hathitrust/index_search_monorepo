
#from ht_full_text_query import get_Solr_query_string

#import Utils
#import Debug.DUtils
#import LS.FacetConfig
#import urllib.parse

import pytest

from ht_full_text_search.ht_full_text_query import HTFullTextQuery


@pytest.fixture(scope="class")
def ht_full_text_query_fixture():
    '''
    Fixture that instantiates the HT Full Text Query class
    :return:
    '''

    query_string = "example query"
    internal = [[1, 234, 4, 456, 563456, 43563, 3456345634]]
    return HTFullTextQuery(query_string, internal)

class TestHTFullTextQuery():

    # Initialize LS::Query::FullText after base class. Use Template Design Pattern.
    def AFTER_Query_initialize(self, C, internal):
        # dummy implementation
        return

    def test_get_solr_query_string(self, ht_full_text_query_fixture):

        query = "q=example query&fl=title,author,date,rights,id,record_no,score&fq=rights:()&version=2.2&start=0&rows=100&indent=off"

        assert query == ht_full_text_query_fixture.get_solr_query_string("C")


