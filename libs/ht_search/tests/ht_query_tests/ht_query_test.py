from ht_search.config_search import FACET_FILTERS_CONFIG_FILE, QUERY_PARAMETER_CONFIG_FILE
from ht_search.ht_query.ht_query import HTSearchQuery


class TestHTSearchQuery:
    def test_query_string_to_dict(self) -> None:
        assert HTSearchQuery.query_string_to_dict("q=*:*&start=0&rows=10&fl=id&indent=on") == {
            "q": "*:*",
            "start": "0",
            "rows": "10",
            "fl": "id",
            "indent": "on",
        }

    def test_query_key_keep_string(self) -> None:
        assert HTSearchQuery().query_string_to_dict(
            'q=_query_:"{!dismax qf=ocr}health"&start=0&rows=10&fl=id&indent=on'
        ) == {
            "q": '_query_:"{!dismax qf=ocr}health"',
            "start": "0",
            "rows": "10",
            "fl": "id",
            "indent": "on",
        }

    def test_create_boost_query_fields(self) -> None:
        data = HTSearchQuery.initialize_solr_query(QUERY_PARAMETER_CONFIG_FILE, conf_query="all")

        assert HTSearchQuery().create_boost_query_fields(data["qf"])[0:3] == [
            "allfieldsProper^2",
            "allfields^1",
            "titleProper^50",
        ]

    def test_facet_creator(self) -> None:
        data = HTSearchQuery.initialize_solr_query(FACET_FILTERS_CONFIG_FILE, conf_query="all")
        assert HTSearchQuery().facet_creator(data["facet"]) == {
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
                "htsource",
                "callnoletters",
            ],
        }

    def test_make_exact_phrase_query_string(self) -> None:
        query_string = "information retrieval"
        assert '"information retrieval"' == HTSearchQuery.get_exact_phrase_query(query_string)

    def test_makey_any_work_query_string(self) -> None:
        query_string = "information retrieval"
        assert HTSearchQuery.manage_string_query(query_string, operator="OR") == {
            "q": "information OR retrieval",
            "q.op": "OR",
        }

    def test_query_filter_creator(self) -> None:
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
            12,
        ]

        assert expected_filter == HTSearchQuery.query_filter_creator_rights(
            filter_name, filter_value
        )
