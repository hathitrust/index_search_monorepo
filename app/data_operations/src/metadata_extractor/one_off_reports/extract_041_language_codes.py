"""Generate the ISO 639 language report from Zephir MARC exports."""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_marc_json_reader import extract_control_number, iter_marc_records
from ht_utils.ht_utils import write_tsv
from pymarc import Field, Record

if TYPE_CHECKING:
    from ..shared import (
        BaseOneOffReport,
        extract_008_language_code,
        extract_041_language_codes,
        extract_oclc_number,
        unique_preserve_order,
    )
else:
    if __package__ in {None, ""}:
        sys.path.append(str(Path(__file__).resolve().parents[2]))
    from metadata_extractor.shared import (
        BaseOneOffReport,
        extract_008_language_code,
        extract_041_language_codes,
        extract_oclc_number,
        unique_preserve_order,
    )

logger = get_ht_logger(name=__name__)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_COLUMNS = [
    "record_id",
    "title",
    "oclc_number",
    "matched_code",
    "set_type",
    "field_041",
    "field_546",
    "rights_code",
]
RIGHTS_CODES = {"pd", "pdus"}
ISO6393_SOURCE = "iso639-3"


class Extract041LanguageCodesReport(BaseOneOffReport):
    def __init__(self) -> None:
        super().__init__(
            default_input_file=PACKAGE_ROOT / "data" / "zephir_full_20260430_vufind.json.gz",
            default_output_file=PACKAGE_ROOT / "output" / "iso639_language_report.tsv",
            default_metadata_file=PACKAGE_ROOT / "output" / "iso639_language_report.metadata.json",
            output_columns=OUTPUT_COLUMNS,
        )

    def build_metadata_summary(
        self,
        *,
        input_file: Path,
        output_file: Path,
        iso6395_file: Path,
        written_rows: int,
    ) -> dict[str, Any]:
        return self.build_base_metadata_summary(
            input_file=input_file,
            output_file=output_file,
            written_rows=written_rows,
            extra_metadata={
                "iso6395_file": str(iso6395_file),
                "set_1": {
                    "name": "iso639-5",
                    "criteria": "008/35-37 or 041$a contains a code from iso639-5.tsv, with 974$r in {pd, pdus}",
                    "include_546_when_present": True,
                },
                "set_2": {
                    "name": "iso639-3",
                    "criteria": "041 second indicator is 7, 041$2 is iso639-3, and 041$a is present, with 974$r in {pd, pdus}",
                    "include_546_when_present": False,
                },
                "row_shape": "one row per record",
                "multiple_match_handling": {
                    "matched_code": "semicolon-separated unique codes in first-seen order",
                    "set_type": "semicolon-separated unique set labels in first-seen order",
                    "field_041": "pipe-separated unique rendered 041 fields in first-seen order",
                },
                "rights_source": "974$r",
            },
        )


REPORT = Extract041LanguageCodesReport()
DEFAULT_ISO6395_FILE = PACKAGE_ROOT / "data" / "iso639-5.tsv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an ISO 639 language report from Zephir MARC JSON."
    )
    parser.add_argument(
        "--input-file",
        "-f",
        type=Path,
        default=REPORT.default_input_file,
        help="Path to the Zephir MARC JSON export (gzipped).",
    )
    parser.add_argument(
        "--output-file",
        "-o",
        type=Path,
        default=REPORT.default_output_file,
        help="TSV file where record metadata will be written.",
    )
    parser.add_argument(
        "--metadata-file",
        "-m",
        type=Path,
        default=REPORT.default_metadata_file,
        help="Metadata document describing the filters used.",
    )
    parser.add_argument(
        "--iso6395-file",
        type=Path,
        default=DEFAULT_ISO6395_FILE,
        help="Path to the ISO 639-5 TSV code list.",
    )
    return parser.parse_args()


def load_iso6395_codes(path: Path) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(f"Cannot find ISO 639-5 code list at {path}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None or "code" not in reader.fieldnames:
            raise ValueError(f"ISO 639-5 file {path} is missing required column 'code'")

        return {(row.get("code") or "").strip().lower() for row in reader}


def extract_rights_code(record: Record) -> str:
    for field in record.get_fields("974"):
        for value in field.get_subfields("r"):
            normalized = value.strip().lower()
            if normalized in RIGHTS_CODES:
                return normalized
    return ""


def is_iso6393_field(field: Field) -> bool:
    indicators = getattr(field, "indicators", None) or [" ", " "]
    if len(indicators) < 2 or indicators[1] != "7":
        return False
    return any(value.strip().lower() == ISO6393_SOURCE for value in field.get_subfields("2"))


def format_fields(fields: Sequence[Field]) -> str:
    return " | ".join(unique_preserve_order(field.format_field() for field in fields))


def build_report_row(
    record: Record,
    *,
    matched_codes: Sequence[str],
    matched_set_types: Sequence[str],
    include_546: bool,
    relevant_041_fields: Sequence[Field],
    rights_code: str,
) -> dict[str, str]:
    return {
        "record_id": extract_control_number(record),
        "title": (record.title or "").strip(),
        "oclc_number": extract_oclc_number(record),
        "matched_code": "; ".join(unique_preserve_order(matched_codes)),
        "set_type": "; ".join(unique_preserve_order(matched_set_types)),
        "field_041": format_fields(relevant_041_fields),
        "field_546": format_fields(record.get_fields("546")) if include_546 else "",
        "rights_code": rights_code,
    }


def match_record(record: Record, iso6395_codes: set[str]) -> dict[str, str] | None:
    rights_code = extract_rights_code(record)
    if rights_code not in RIGHTS_CODES:
        return None

    matched_codes: list[str] = []
    matched_set_types: list[str] = []
    relevant_041_fields: list[Field] = []
    set1_matched = False

    code_008 = extract_008_language_code(record)
    if code_008 and code_008 in iso6395_codes:
        matched_codes.append(code_008)
        matched_set_types.append("iso639-5")
        set1_matched = True

    for field in record.get_fields("041"):
        field_codes = extract_041_language_codes(field)
        iso6395_matches = [code for code in field_codes if code in iso6395_codes]
        if iso6395_matches:
            matched_codes.extend(iso6395_matches)
            matched_set_types.append("iso639-5")
            relevant_041_fields.append(field)
            set1_matched = True

        if is_iso6393_field(field) and field_codes:
            matched_codes.extend(field_codes)
            matched_set_types.append("iso639-3")
            relevant_041_fields.append(field)

    matched_codes = unique_preserve_order(matched_codes)
    matched_set_types = unique_preserve_order(matched_set_types)
    relevant_041_fields = [
        field
        for index, field in enumerate(relevant_041_fields)
        if field not in relevant_041_fields[:index]
    ]
    if not matched_codes or not matched_set_types:
        return None

    return build_report_row(
        record,
        matched_codes=matched_codes,
        matched_set_types=matched_set_types,
        include_546=set1_matched,
        relevant_041_fields=relevant_041_fields,
        rights_code=rights_code,
    )


def generate_relevant_rows(path: Path, iso6395_codes: set[str]) -> Iterable[dict[str, str]]:
    for record in iter_marc_records(path):
        row = match_record(record, iso6395_codes)
        if row is not None:
            yield row


def main() -> None:
    args = parse_args()
    logger.info("Reading Zephir export from %s", args.input_file)
    iso6395_codes = load_iso6395_codes(args.iso6395_file)
    rows_path, written_rows = write_tsv(
        generate_relevant_rows(args.input_file, iso6395_codes),
        args.output_file,
        columns_name=OUTPUT_COLUMNS,
    )
    metadata_summary = REPORT.build_metadata_summary(
        input_file=args.input_file,
        output_file=rows_path,
        iso6395_file=args.iso6395_file,
        written_rows=written_rows,
    )
    REPORT.write_metadata_summary(args.metadata_file, metadata_summary)
    logger.info("Generated %d language-report rows at %s", written_rows, rows_path)


if __name__ == "__main__":
    main()
