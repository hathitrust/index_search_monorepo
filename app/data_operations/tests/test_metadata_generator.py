import gzip
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ht_utils.ht_marc_json_reader import dict_to_pymarc_record
from metadata_extractor.metadata_generator import (
    DEFAULT_KEYWORDS,
    extract_identifiers,
    generate_dissertation_rows,
    record_matches,
)
from pymarc import Field, Record, Subfield

SAMPLE_RECORD = {
    "leader": "00000nam a2200000 a 4500",
    "fields": [
        {"001": "0000001"},
        {"035": {"subfields": [{"a": "(ProQuest)disstheses AAI1234567"}]}},
        {"245": {"subfields": [{"a": "Dissertation Title"}]}},
        {"100": {"subfields": [{"a": "Doe, John"}]}},
        {"502": {"subfields": [{"a": "viii, 200 p.", "o": "AAI1234567"}]}},
        {"260": {"subfields": [{"c": "2022"}]}},
        {"650": {"subfields": [{"a": "History"}]}},
    ],
}

NON_DISSERTATION_RECORD = {
    "leader": "00000nam a2200000 a 4500",
    "fields": [
        {"001": "0000002"},
        {"035": {"subfields": [{"a": "Other ID"}]}},
        {"245": {"subfields": [{"a": "General Title"}]}},
        {"100": {"subfields": [{"a": "Smith, Jane"}]}},
    ],
}


def write_sample(path: Path, records: Sequence[dict[str, Any]]) -> Path:
    payload = "\n".join(json.dumps(record) for record in records)
    path.write_bytes(gzip.compress(payload.encode("utf-8")))
    return path


def test_record_matches_detects_dissertation_keywords() -> None:
    row = SAMPLE_RECORD.copy()

    record = dict_to_pymarc_record(row)

    assert record_matches(record, DEFAULT_KEYWORDS)

    no_dissertation_record = dict_to_pymarc_record(NON_DISSERTATION_RECORD)
    assert not record_matches(no_dissertation_record, DEFAULT_KEYWORDS)


def test_extract_identifiers() -> None:

    record = Record()
    record.add_field(Field(tag="035", indicators=[" ", " "], subfields=[Subfield(code="a", value="(ProQuest)disstheses AAI999")]))  # type: ignore[no-untyped-call,arg-type]
    record.add_field(Field(tag="502", indicators=[" ", " "], subfields=[Subfield(code="o", value="AAI8999")]))  # type: ignore[no-untyped-call,arg-type]
    record.add_field(Field(tag="035", indicators=[" ", " "], subfields=[Subfield(code="a", value="(MiU)990027275210106381")]))  # type: ignore[no-untyped-call,arg-type]

    identifiers = extract_identifiers(record)
    assert "(ProQuest)disstheses AAI999" in identifiers
    assert "AAI8999" in identifiers
    assert "(MiU)990027275210106381" in identifiers

def test_generate_dissertation_rows(tmp_path: Path) -> None:
    gzipped = tmp_path / "sample.json.gz"
    write_sample(gzipped, [SAMPLE_RECORD, NON_DISSERTATION_RECORD])
    rows = list(generate_dissertation_rows(gzipped))
    assert len(rows) == 1
    row = rows[0]
    assert row["title"] == "Dissertation Title"
    assert "History" in row["discipline"]
    assert row["other_sources"] == "AAI1234567; (ProQuest)disstheses AAI1234567"
    assert row["year_published"] == "2022"
