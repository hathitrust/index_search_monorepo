import pytest

from ht_query.ht_query import HTSearchQuery, QUERY_PARAMETER_CONFIG_FILE, FACET_FILTERS_CONFIG_FILE


class TestHTSearchQuery:
    def test_query_string_to_dict(self):
        assert HTSearchQuery().query_string_to_dict(
            "q=*:*&start=0&rows=10&fl=id&indent=on"
        ) == {"q": "*:*", "start": "0", "rows": "10", "fl": "id", "indent": "on"}

    def test_query_key_keep_string(self):
        assert HTSearchQuery().query_string_to_dict(
            'q=_query_:"{!dismax qf=ocr}health"&start=0&rows=10&fl=id&indent=on'
        ) == {
            "q": '_query_:"{!dismax qf=ocr}health"',
            "start": "0",
            "rows": "10",
            "fl": "id",
            "indent": "on",
        }

    def test_create_boost_query_fields(self):

        data = HTSearchQuery.initialize_solr_query(QUERY_PARAMETER_CONFIG_FILE, conf_query="all")

        assert HTSearchQuery().create_boost_query_fields(data['qf'])[0:3] == ["allfieldsProper^2", "allfields^1", "titleProper^50"]

    def test_facet_creator(self):

        data = HTSearchQuery.initialize_solr_query(FACET_FILTERS_CONFIG_FILE, conf_query="all")
        assert HTSearchQuery().facet_creator(data['facet']) == {
            "facet.mincount": 1,
            "facet": "on",
            "facet.limit": 30,
            "facet.field": [
                "topicStr",
                "authorStr",
                "language008_full",
                "countryOfPubStr",
                "bothPublishDateRange",
                "format",
                "htsource"]
        }

    def test_get_boolean_expression(self):
        assert HTSearchQuery().get_boolean_opperator("hola") == "(\"hola\")"
        assert HTSearchQuery().get_boolean_opperator("hola chico") == "(\"hola\" OR \"chico\")"
        assert HTSearchQuery().get_boolean_opperator("hola chico majadero") == "(\"hola\" OR \"chico\" OR \"majadero\")"


    def test_query_json_format(self):
        # query = curl "http://localhost:8983/solr/tmdb/query?" -d '{	"query": {		"bool": {			"must": [				{ "edismax": 					{  "qf": "title genres",					   "query":"breakfast"					}				},				{ "edismax": 					{  "qf": "title genres",					   "query":"comedy"					}				}							]		}	}	}'
        # JSON Query DSL in verbose way, it is better to understand the query
        json_query = {
            "query": {
                "edismax": {  # query parser
                    "qf": "ocr",  # qf = query fields
                    "query": "26th Regiment of Foot",  # query = query string
                    "mm": "100%25",  # mm = minimum match
                    "tie": "0.9",  # tie = tie breaker
                },
                "fl": ["author", "id", "title"],  # fl = fields to return
            },
            "start": "0",
            "rows": "10",
            "fl": "id",
            "indent": "on",
        }

    def test_make_exact_phrase_query_string(self):
        query_string = "information retrieval"
        assert '"information retrieval"' == HTSearchQuery.get_exact_phrase_query(query_string) #'"'.join(("", query_string, ""))

    def test_makey_any_work_query_string(self):
        query_string = "information retrieval"
        assert "information OR retrieval" == query_string.replace(" ", " OR ")

    def test_make_all_these_word_query_string(self):
        query_string = "information retrieval"
        assert "information retrieval" == "information retrieval"

    def test_query_filter_creator(self):
        expected_filter = "rights:(25 OR 15 OR 18 OR 1 OR 21 OR 23 OR 19 OR 13 OR 11 OR 20 OR 7 OR 10 OR 24 OR 14 OR 17 OR 22 OR 12)"
        filter_name = "rights"
        filter_value = [
            25,
            15,
            18,
            1,
            21,
            23,
            19,
            13,
            11,
            20,
            7,
            10,
            24,
            14,
            17,
            22,
            12
        ]

        assert expected_filter == HTSearchQuery().query_filter_creator(filter_name, filter_value)


