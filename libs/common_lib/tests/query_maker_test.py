from ht_utils.query_maker import make_query, make_solr_term_query

# --- make_query ---------------------------------------------------------


def test_make_query_single_document_defaults_to_ht_id_field() -> None:
    assert make_query(["item1"]) == "ht_id:item1"


def test_make_query_single_document_is_not_quoted() -> None:
    # Unlike the multi-document branch below, a single value is interpolated
    # without surrounding quotes.
    assert make_query(["item with spaces"]) == "ht_id:item with spaces"


def test_make_query_multiple_documents_are_quoted_and_or_joined() -> None:
    assert make_query(["item1", "item2"]) == 'ht_id:("item1" OR "item2")'


def test_make_query_by_field_record_uses_id_field() -> None:
    assert make_query(["rec1"], by_field="record") == "id:rec1"


def test_make_query_unrecognised_by_field_silently_falls_back_to_ht_id() -> None:
    """query_field starts as "ht_id" and only ever gets overwritten for
    by_field == "record"; any other value -- including a typo like "records"
    -- silently produces an ht_id query instead of raising.
    """
    assert make_query(["item1"], by_field="records") == "ht_id:item1"
    assert make_query(["item1"], by_field="bogus") == "ht_id:item1"


def test_make_query_empty_list_produces_empty_quoted_clause() -> None:
    assert make_query([]) == 'ht_id:("")'


def test_make_query_escapes_solr_special_characters() -> None:
    # The single-character reserved symbols
    assert make_query(["a+b"]) == "ht_id:a\\+b"
    assert make_query(["a-b"]) == "ht_id:a\\-b"
    assert make_query(["a!b"]) == "ht_id:a\\!b"
    assert make_query(["a(b)c"]) == "ht_id:a\\(b\\)c"
    assert make_query(["a{b}c"]) == "ht_id:a\\{b\\}c"
    assert make_query(["a[b]c"]) == "ht_id:a\\[b\\]c"
    assert make_query(["a^b"]) == "ht_id:a\\^b"
    assert make_query(['a"b']) == 'ht_id:a\\"b'
    assert make_query(["a~b"]) == "ht_id:a\\~b"
    assert make_query(["a*b"]) == "ht_id:a\\*b"
    assert make_query(["a?b"]) == "ht_id:a\\?b"
    assert make_query(["a:b"]) == "ht_id:a\\:b"
    assert make_query(["a\\b"]) == "ht_id:a\\\\b"
    assert make_query(["a/b"]) == "ht_id:a\\/b"
    # The two-character reserved symbols
    assert make_query(["a&&b"]) == "ht_id:a\\&\\&b"
    assert make_query(["a||b"]) == "ht_id:a\\|\\|b"


# --- make_solr_term_query ------------------------------------------------


def test_make_solr_term_query_single_document_defaults_to_ht_id_field() -> None:
    assert make_solr_term_query(["item1"]) == "{!terms f=ht_id}item1"


def test_make_solr_term_query_multiple_documents_are_comma_joined() -> None:
    assert make_solr_term_query(["item1", "item2"]) == "{!terms f=ht_id}item1,item2"


def test_make_solr_term_query_by_field_record_uses_id_field() -> None:
    assert make_solr_term_query(["rec1", "rec2"], by_field="record") == "{!terms f=id}rec1,rec2"


def test_make_solr_term_query_by_field_item_uses_ht_id_field() -> None:
    # by_field="item" is the default; exercised explicitly here rather than only via
    # omission, mirroring the by_field="record" test above.
    assert (
        make_solr_term_query(["item1", "item2"], by_field="item") == "{!terms f=ht_id}item1,item2"
    )


def test_make_solr_term_query_unrecognised_by_field_falls_back_to_ht_id() -> None:
    assert make_solr_term_query(["item1"], by_field="bogus") == "{!terms f=ht_id}item1"


def test_make_solr_term_query_empty_list_produces_empty_term_list() -> None:
    assert make_solr_term_query([]) == "{!terms f=ht_id}"


def test_make_solr_term_query_escapes_commas_within_an_id() -> None:
    assert make_solr_term_query(["ab,cd", "ef"]) == "{!terms f=ht_id}ab\\,cd,ef"
