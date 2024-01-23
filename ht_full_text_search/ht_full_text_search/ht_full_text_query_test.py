import pytest

from config_search import QUERY_PARAMETER_CONFIG_FILE, FACET_FILTERS_CONFIG_FILE

class TestHTFullTextQuery():

    def test_full_text_search_default_values(self, ht_full_text_query_default_values):

            assert ht_full_text_query_default_values.config_query == "all"
            assert ht_full_text_query_default_values.solr_facet_filters == {}

    def test_full_text_search_query_parameters(self, ht_full_text_query):

        query_dict = ht_full_text_query.make_solr_query(query_string="query_example",
                                                  operator="AND")
        assert query_dict.get('defType') == 'edismax'
        assert query_dict.get('tie') == 0.5