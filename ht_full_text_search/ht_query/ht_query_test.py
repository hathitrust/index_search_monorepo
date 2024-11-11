from ht_query.ht_query import HTSearchQuery
from config_search import QUERY_PARAMETER_CONFIG_FILE, FACET_FILTERS_CONFIG_FILE


def ht_search_query_object():
    """
    Fixture that instantiates the HTFullTextQuery class
    :return:
    """

    return HTSearchQuery(
        config_query="all",
        config_query_path=QUERY_PARAMETER_CONFIG_FILE,
        user_id=None,
        config_facet_field="all",
        config_facet_field_path=FACET_FILTERS_CONFIG_FILE,
    )


class TestHTSearchQuery:
    def test_query_string_to_dict(self):
        assert HTSearchQuery.query_string_to_dict(
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
        data = HTSearchQuery.initialize_solr_query(
            QUERY_PARAMETER_CONFIG_FILE, conf_query="all"
        )

        assert HTSearchQuery().create_boost_query_fields(data["qf"])[0:3] == [
            "allfieldsProper^2",
            "allfields^1",
            "titleProper^50",
        ]


    def test_facet_creator(self):
        data = HTSearchQuery.initialize_solr_query(
            FACET_FILTERS_CONFIG_FILE, conf_query="all"
        )
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
                "callnoletters"
            ],
        }

    def test_make_exact_phrase_query_string(self):
        query_string = "information retrieval"
        assert '"information retrieval"' == HTSearchQuery.get_exact_phrase_query(
            query_string
        )

    def test_makey_any_work_query_string(self):
        query_string = "information retrieval"
        assert "information OR retrieval" == query_string.replace(" ", " OR ")

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
            12,
        ]

        assert expected_filter == HTSearchQuery.query_filter_creator_rights(
            filter_name, filter_value
        )
