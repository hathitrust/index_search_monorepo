import pytest

from config_search import QUERY_PARAMETER_CONFIG_FILE, FACET_FILTERS_CONFIG_FILE


class TestHTFullTextQuery:
    def test_full_text_search_default_values(self, ht_full_text_query_default_values):
        assert ht_full_text_query_default_values.config_query == "all"
        assert ht_full_text_query_default_values.solr_facet_filters == {}

    def test_full_text_search_query_parameters(self, ht_full_text_query):
        query_dict = ht_full_text_query.make_solr_query(
            query_string="query_example", operator="AND"
        )
        assert query_dict.get("defType") == "edismax"
        assert query_dict.get("tie") == 0.5

    def test_full_text_search_query_parameters_with_filters(self, ht_full_text_query):
        query_dict = ht_full_text_query.make_solr_query(
            query_string="query_example", operator="AND", query_filter=True, filter_dict={"id": ["umn.31951002065930r",
                                                                                           "umn.31951d031321278"]}
        )
        assert query_dict.get("defType") == "edismax"
        assert query_dict.get("tie") == 0.5
        assert query_dict.get("fq") == 'id:(umn.31951002065930r OR umn.31951d031321278)'

    def test_full_text_search_query_string_solr6(self, ht_full_text_query):
        query_string = ht_full_text_query.manage_string_query_solr6(input_phrase="query example", operator="AND")

        #assert query_string == "query AND example"
        assert query_string == "(query) AND (example)"

        query_string = ht_full_text_query.manage_string_query_solr6(input_phrase="query example", operator="OR")

        #assert query_string == "query OR example"
        assert query_string == "(query) OR (example)"

        query_string = ht_full_text_query.manage_string_query_solr6(input_phrase="query example", operator=None)

        assert query_string == "\"query example\""