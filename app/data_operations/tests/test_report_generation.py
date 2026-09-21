import pytest
from ht_utils.ht_marc_json_reader import dict_to_pymarc_record
from metadata_extractor.report_generation import (
    extract_008_language_code,
    extract_oclc_number,
    get_041_codes,
    is_iso6393_field,
    match_record,
)
from pymarc import Field, Indicators, Record, Subfield

ISO6395_CODES = {"eng", "fre"}


def field_008(value: str) -> Field:
    return Field(tag="008", data=value)


def field_041(subfields: list[Subfield], ind1: str = " ", ind2: str = " ") -> Field:
    return Field(tag="041", indicators=Indicators(ind1, ind2), subfields=subfields)


# --- extract_008_language_code -------------------------------------------------


def test_extract_008_language_code_reads_offset_35_to_38() -> None:
    record = Record()
    record.add_field(field_008("0" * 35 + "eng"))  # type: ignore[no-untyped-call]

    assert extract_008_language_code(record) == "eng"


def test_extract_008_language_code_strips_and_lowercases() -> None:
    record = Record()
    record.add_field(field_008("0" * 35 + "EN "))  # type: ignore[no-untyped-call]

    assert extract_008_language_code(record) == "en"


def test_extract_008_language_code_missing_field_returns_empty() -> None:
    record = Record()

    assert extract_008_language_code(record) == ""


def test_extract_008_language_code_too_short_returns_empty() -> None:
    record = Record()
    record.add_field(field_008("x" * 30))  # type: ignore[no-untyped-call]

    assert extract_008_language_code(record) == ""


# --- extract_oclc_number ---------------------------------------------------


@pytest.mark.parametrize(
    ("subfield_code", "value", "expected"),
    [
        ("a", "(OCoLC)ocm12345678", "12345678"),
        ("a", "(OCoLC)on003456789", "003456789"),
        ("z", "(OCoLC)12345678", "12345678"),
        ("a", "ocm12345678", "12345678"),
        ("a", "12345678", "12345678"),
    ],
)
def test_extract_oclc_number_matches(subfield_code: str, value: str, expected: str) -> None:
    record = Record()
    record.add_field(  # type: ignore[no-untyped-call]
        Field(
            tag="035",
            indicators=Indicators(" ", " "),
            subfields=[Subfield(code=subfield_code, value=value)],
        )
    )

    assert extract_oclc_number(record) == expected


def test_extract_oclc_number_no_digits_returns_empty() -> None:
    record = Record()
    record.add_field(  # type: ignore[no-untyped-call]
        Field(
            tag="035",
            indicators=Indicators(" ", " "),
            subfields=[Subfield(code="a", value="(ProQuest)disstheses")],
        )
    )

    assert extract_oclc_number(record) == ""


def test_extract_oclc_number_fallback_regex_matches_a_bare_year() -> None:
    """Documents a known false positive: the fallback pattern
    \\b(?:oc[mn]|on)?(\\d{4,})\\b matches any 4+ digit run, including a year
    mentioned in a 035 note with no OCoLC prefix at all.
    """
    record = Record()
    record.add_field(  # type: ignore[no-untyped-call]
        Field(
            tag="035",
            indicators=Indicators(" ", " "),
            subfields=[Subfield(code="a", value="Reprint of the 1975 edition")],
        )
    )

    assert extract_oclc_number(record) == "1975"


# --- is_iso6393_field --------------------------------------------------------


def test_is_iso6393_field_true_when_ind2_is_7_and_source_is_iso639_3() -> None:
    field = field_041(
        [Subfield(code="a", value="fra"), Subfield(code="2", value="iso639-3")], ind2="7"
    )

    assert is_iso6393_field(field)


def test_is_iso6393_field_source_match_is_case_insensitive() -> None:
    field = field_041(
        [Subfield(code="a", value="fra"), Subfield(code="2", value="ISO639-3")], ind2="7"
    )

    assert is_iso6393_field(field)


def test_is_iso6393_field_false_when_source_subfield_missing() -> None:
    field = field_041([Subfield(code="a", value="fra")], ind2="7")

    assert not is_iso6393_field(field)


def test_is_iso6393_field_false_when_ind2_is_not_7() -> None:
    field = field_041(
        [Subfield(code="a", value="fra"), Subfield(code="2", value="iso639-3")], ind2=" "
    )

    assert not is_iso6393_field(field)


# --- get_041_codes -----------------------------------------------------------


def test_get_041_codes_dedupes_and_normalizes_case_and_whitespace() -> None:
    field = field_041(
        [
            Subfield(code="a", value="eng"),
            Subfield(code="a", value=" ENG "),
            Subfield(code="a", value="fre"),
        ]
    )

    assert get_041_codes(field) == ["eng", "fre"]


def test_get_041_codes_ignores_non_a_subfields() -> None:
    field = field_041([Subfield(code="a", value="eng"), Subfield(code="h", value="pol")])

    assert get_041_codes(field) == ["eng"]


# --- match_record (integration over the whole matching pipeline) ------------


def _record(fields: list[dict]) -> Record:
    return dict_to_pymarc_record(
        {
            "leader": "00000nam a2200000 a 4500",
            "fields": fields,
        }
    )


def test_match_record_returns_none_when_rights_code_not_pd_or_pdus() -> None:
    record = _record(
        [
            {"001": "0000001"},
            {"974": {"subfields": [{"r": "ic"}]}},
        ]
    )
    record.add_field(field_008("0" * 35 + "eng"))  # type: ignore[no-untyped-call]

    assert match_record(record, ISO6395_CODES) is None


def test_match_record_matches_via_008_and_includes_546() -> None:
    record = _record(
        [
            {"001": "0000001"},
            {"245": {"subfields": [{"a": "A Title"}]}},
            {"974": {"subfields": [{"r": "pd"}]}},
            {"546": {"subfields": [{"a": "In English."}]}},
        ]
    )
    record.add_field(field_008("0" * 35 + "eng"))  # type: ignore[no-untyped-call]

    row = match_record(record, ISO6395_CODES)

    assert row is not None
    assert row["record_id"] == "0000001"
    assert row["matched_code"] == "eng"
    assert row["set_type"] == "iso639-5"
    assert row["field_041"] == ""
    assert row["field_546"] != ""
    assert row["rights_code"] == "pd"


def test_match_record_matches_via_041_iso6395_code() -> None:
    record = _record(
        [
            {"001": "0000002"},
            {"041": {"subfields": [{"a": "fre"}]}},
            {"974": {"subfields": [{"r": "pdus"}]}},
        ]
    )

    row = match_record(record, ISO6395_CODES)

    assert row is not None
    assert row["matched_code"] == "fre"
    assert row["set_type"] == "iso639-5"
    assert row["field_041"] != ""


def test_match_record_matches_via_iso6393_only_excludes_546() -> None:
    record = _record(
        [
            {"001": "0000003"},
            {"041": {"ind2": "7", "subfields": [{"a": "gsl"}, {"2": "iso639-3"}]}},
            {"974": {"subfields": [{"r": "pd"}]}},
            {"546": {"subfields": [{"a": "Sign language note."}]}},
        ]
    )

    row = match_record(record, ISO6395_CODES)

    assert row is not None
    assert row["matched_code"] == "gsl"
    assert row["set_type"] == "iso639-3"
    # set 2 matches don't set set1_matched, so 546 must not be included.
    assert row["field_546"] == ""


def test_match_record_same_041_field_matching_both_sets_is_not_duplicated() -> None:
    record = _record(
        [
            {"001": "0000004"},
            {"041": {"ind2": "7", "subfields": [{"a": "fre"}, {"2": "iso639-3"}]}},
            {"974": {"subfields": [{"r": "pd"}]}},
        ]
    )

    row = match_record(record, ISO6395_CODES)

    assert row is not None
    assert sorted(row["set_type"].split("; ")) == ["iso639-3", "iso639-5"]
    # The same physical 041 field matched both sets; it should be rendered once,
    # not twice joined by " | ".
    assert row["field_041"] == "fre iso639-3"


def test_match_record_returns_none_when_no_language_matches() -> None:
    record = _record(
        [
            {"001": "0000005"},
            {"041": {"subfields": [{"a": "spa"}]}},
            {"974": {"subfields": [{"r": "pd"}]}},
        ]
    )

    assert match_record(record, ISO6395_CODES) is None
