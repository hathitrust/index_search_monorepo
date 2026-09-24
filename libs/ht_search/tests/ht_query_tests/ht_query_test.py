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

    def test_create_boost_phrase_fields(self) -> None:
        assert (
            HTSearchQuery.create_boost_phrase_fields([["field1", 2], ["field2", 3]])
            == "field1^2 field2^3"
        )

    def test_create_boost_phrase_fields_empty_list(self) -> None:
        assert HTSearchQuery.create_boost_phrase_fields([]) == ""

    def test_create_params_dict_missing_qf_and_pf_does_not_raise(self) -> None:
        """Regression test: create_params_dict used to call
        create_boost_phrase_fields(self.solr_parameters.get("qf")) unguarded, so a config
        with no "qf" entry raised a TypeError from map(str, None). Both qf and pf are now
        guarded with `if qf else []`; this pins that fix so it cannot regress.
        """
        query = HTSearchQuery()
        assert query.solr_parameters == {}

        params = query.create_params_dict()

        assert params["qf"] == []
        assert params["pf"] == []

    def test_create_params_dict_formats_qf_and_pf_when_present(self) -> None:
        query = HTSearchQuery()
        query.solr_parameters = {"qf": [["field1", 2]], "pf": [["field2", 3]]}

        params = query.create_params_dict()

        assert params["qf"] == "field1^2"
        assert params["pf"] == "field2^3"

    def test_query_filter_creator_string_with_list(self) -> None:
        assert HTSearchQuery.query_filter_creator_string("id", ["a", "b"]) == 'id:("a" OR "b")'

    def test_query_filter_creator_string_with_single_value(self) -> None:
        assert HTSearchQuery.query_filter_creator_string("id", "a") == 'id:("a")'

    def test_manage_string_query_exact_phrase_when_operator_none(self) -> None:
        assert HTSearchQuery.manage_string_query("information retrieval") == {
            "q": '"information retrieval"'
        }

    def test_manage_string_query_and_operator(self) -> None:
        assert HTSearchQuery.manage_string_query("information retrieval", operator="AND") == {
            "q": "information AND retrieval",
            "q.op": "AND",
        }

    def test_manage_string_query_unsupported_operator_is_used_as_is(self) -> None:
        """Unlike manage_string_query_solr6, manage_string_query does no operator
        validation -- any non-None operator string is used verbatim to join the
        words and set q.op, rather than being rejected or falling back to None.
        """
        assert HTSearchQuery.manage_string_query("information retrieval", operator="XOR") == {
            "q": "information XOR retrieval",
            "q.op": "XOR",
        }

    def test_manage_string_query_collapses_whitespace_when_operator_given(self) -> None:
        assert HTSearchQuery.manage_string_query("  information   retrieval  ", operator="AND") == {
            "q": "information AND retrieval",
            "q.op": "AND",
        }

    def test_manage_string_query_preserves_whitespace_for_exact_phrase(self) -> None:
        # Unlike the operator branch (which splits/rejoins on whitespace), the
        # exact-phrase (operator=None) branch wraps input_phrase as-is in quotes.
        assert HTSearchQuery.manage_string_query("  information retrieval  ") == {
            "q": '"  information retrieval  "'
        }

    def test_manage_string_query_solr6_or_and_and(self) -> None:
        assert (
            HTSearchQuery.manage_string_query_solr6("information retrieval", operator="OR")
            == "information OR retrieval"
        )
        assert (
            HTSearchQuery.manage_string_query_solr6("information retrieval", operator="AND")
            == "information AND retrieval"
        )

    def test_manage_string_query_solr6_none_operator_is_exact_phrase(self) -> None:
        assert (
            HTSearchQuery.manage_string_query_solr6("information retrieval")
            == '"information retrieval"'
        )

    def test_manage_string_query_solr6_collapses_whitespace_for_or_and_and(self) -> None:
        assert (
            HTSearchQuery.manage_string_query_solr6("  information   retrieval  ", operator="OR")
            == "information OR retrieval"
        )

    def test_manage_string_query_solr6_preserves_whitespace_for_exact_phrase(self) -> None:
        # Same asymmetry as manage_string_query: the None-operator branch wraps
        # input_phrase as-is, it doesn't split()/rejoin like the OR/AND branch does.
        assert (
            HTSearchQuery.manage_string_query_solr6("  information retrieval  ")
            == '"  information retrieval  "'
        )

    def test_manage_string_query_solr6_unrecognised_operator_returns_none(self) -> None:
        """Any operator other than "OR", "AND" or None falls through to an implicit (now
        explicit) None return -- a caller passing an unexpected operator value silently
        gets None back instead of a query string or an error.
        """
        assert (
            HTSearchQuery.manage_string_query_solr6("information retrieval", operator="XOR") is None
        )
