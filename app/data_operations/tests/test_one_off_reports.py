import json
from pathlib import Path

from metadata_extractor.one_off_reports.extract_041_language_codes import (
    OUTPUT_COLUMNS,
    Extract041LanguageCodesReport,
    load_iso6395_codes,
    match_record,
)
from metadata_extractor.shared import (
    extract_008_language_code,
    extract_041_language_codes,
    extract_oclc_number,
    unique_preserve_order,
)
from pymarc import Field, Indicators, Record, Subfield


def build_language_record() -> Record:
    record = Record()
    record.add_field(Field(tag="001", data="0000003"))  # type: ignore[no-untyped-call]
    record.add_field(Field(tag="008", data=(" " * 35) + "gemxx"))  # type: ignore[no-untyped-call]
    record.add_field(
        Field(
            tag="035",
            indicators=Indicators(" ", " "),
            subfields=[Subfield(code="a", value="(OCoLC)ocm1234567")],
        )
    )  # type: ignore[no-untyped-call]
    record.add_field(
        Field(
            tag="245",
            indicators=Indicators("0", "0"),
            subfields=[Subfield(code="a", value="Polyglot title")],
        )
    )  # type: ignore[no-untyped-call]
    record.add_field(
        Field(
            tag="041",
            indicators=Indicators("0", "7"),
            subfields=[
                Subfield(code="a", value="fra"),
                Subfield(code="a", value="gsl"),
                Subfield(code="2", value="iso639-3"),
            ],
        )
    )  # type: ignore[no-untyped-call]
    record.add_field(
        Field(
            tag="546",
            indicators=Indicators(" ", " "),
            subfields=[Subfield(code="a", value="Text in multiple languages.")],
        )
    )  # type: ignore[no-untyped-call]
    record.add_field(
        Field(
            tag="974",
            indicators=Indicators(" ", " "),
            subfields=[Subfield(code="r", value="pdus")],
        )
    )  # type: ignore[no-untyped-call]
    return record


def test_shared_marc_helpers_extract_expected_values() -> None:
    field_041 = Field(
        tag="041",
        indicators=Indicators("0", "0"),
        subfields=[
            Subfield(code="a", value=" eng "),
            Subfield(code="a", value="fre"),
            Subfield(code="a", value="eng"),
        ],
    )

    record = Record()
    record.add_field(Field(tag="008", data=(" " * 35) + "engxx"))  # type: ignore[no-untyped-call]
    record.add_field(field_041)  # type: ignore[no-untyped-call]
    record.add_field(
        Field(
            tag="035",
            indicators=Indicators(" ", " "),
            subfields=[Subfield(code="a", value="(OCoLC)on123456789")],
        )
    )  # type: ignore[no-untyped-call]

    assert unique_preserve_order(["eng", "fre", "eng", ""]) == ["eng", "fre"]
    assert extract_oclc_number(record) == "123456789"
    assert extract_008_language_code(record) == "eng"
    assert extract_041_language_codes(field_041) == ["eng", "fre"]


def test_language_report_match_record_preserves_row_shape() -> None:
    row = match_record(build_language_record(), {"gem"})

    assert row is not None
    assert list(row) == OUTPUT_COLUMNS
    assert row["record_id"] == "0000003"
    assert row["title"] == "Polyglot title"
    assert row["oclc_number"] == "1234567"
    assert row["matched_code"] == "gem; fra; gsl"
    assert row["set_type"] == "iso639-5; iso639-3"
    assert "Text in multiple languages." in row["field_546"]
    assert row["rights_code"] == "pdus"


def test_language_report_metadata_summary_uses_shared_writer(tmp_path: Path) -> None:
    report = Extract041LanguageCodesReport()
    metadata_file = tmp_path / "report.metadata.json"
    summary = report.build_metadata_summary(
        input_file=Path("input.json.gz"),
        output_file=Path("output.tsv"),
        iso6395_file=Path("iso639-5.tsv"),
        written_rows=3,
    )

    written = report.write_metadata_summary(metadata_file, summary)

    assert written == metadata_file
    assert json.loads(metadata_file.read_text(encoding="utf-8")) == summary
    assert summary["column_order"] == OUTPUT_COLUMNS
    assert summary["written_rows"] == 3


def test_load_iso6395_codes_reads_code_column(tmp_path: Path) -> None:
    iso_file = tmp_path / "iso639-5.tsv"
    iso_file.write_text("alpha3\tcode\nignored\tgem\nignored\tira\n", encoding="utf-8")

    assert load_iso6395_codes(iso_file) == {"gem", "ira"}
