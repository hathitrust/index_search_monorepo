"""Generate an ISO 639-3 / ISO 639-5 language report from Zephir MARC exports."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from ht_utils.ht_logger import get_ht_logger
from metadata_extractor.one_off_reports.ht_marc_json_reader import extract_control_number, iter_marc_records
from ht_utils.ht_utils import write_metadata_summary, write_tsv
from pymarc import Field, Record

logger = get_ht_logger(name=__name__)

DEFAULT_INPUT_FILE = Path(__file__).parent / "data" / "zephir_full_20260430_vufind.json.gz"
DEFAULT_OUTPUT_FILE = Path(__file__).parent / "output" / "iso639_language_report.tsv"
DEFAULT_METADATA_FILE = Path(__file__).parent / "output" / "iso639_language_report.metadata.json"
# I am using this file to match the language code
DEFAULT_ISO6395_FILE = Path(__file__).parent / "data" / "iso639-5.tsv"

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an ISO 639 language report from Zephir MARC JSON."
    )
    parser.add_argument(
        "--input-file",
        "-f",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help="Path to the Zephir MARC JSON export (gzipped).",
    )
    parser.add_argument(
        "--output-file",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="TSV file where record metadata will be written.",
    )
    parser.add_argument(
        "--metadata-file",
        "-m",
        type=Path,
        default=DEFAULT_METADATA_FILE,
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

        # Load the language code to compare with the MARC language codes.
        codes = {(row.get("code") or "").strip().lower() for row in reader}

    return codes


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    ordered: dict[str, None] = {}
    for value in values:
        cleaned = value.strip()
        if cleaned:
            ordered.setdefault(cleaned, None)
    return list(ordered)


def extract_rights_code(record: Record) -> str:
    """Extract the rights code from a MARC record as a string.
    # =974  \\$bMIU$cMIU$d20260228$sgoogle$umdp.39015006324142$zv.2$y1968$rpdus$qgfv
    """

    for field in record.get_fields("974"):
        for value in field.get_subfields("r"):
            normalized = value.strip().lower()
            if normalized in RIGHTS_CODES:
                return normalized
    return ""


def extract_oclc_number(record: Record) -> str:
    for field in record.get_fields("035"):
        for code in ("a", "z"):
            for value in field.get_subfields(code):
                cleaned = value.strip()
                if not cleaned:
                    continue
                match = re.search(r"\(OCoLC\)(?:oc[mn]|on)?(\d+)", cleaned, flags=re.IGNORECASE)
                if match:
                    return match.group(1)
                fallback = re.search(r"\b(?:oc[mn]|on)?(\d{4,})\b", cleaned, flags=re.IGNORECASE)
                if fallback:
                    return fallback.group(1)
    return ""


def extract_008_language_code(record: Record) -> str:
    """
    Extract the language code from a MARC record as a string.
    """
    field_008 = record.get_fields("008")
    if not field_008:
        return ""
    value = field_008[0].value()
    # The field_008 len should be 35-37?
    if not value or len(value) < 38:
        return ""
    return value[35:38].strip().lower()


def get_041_codes(field: Field) -> list[str]:
    """

    Retrieve all the language codes from a MARC record as a list.

    Example:
    041	1	⊔	‡aeng ‡hpol
    041 1# $a eng $a fre $h ger $b eng

    """
    return unique_preserve_order(value.strip().lower() for value in field.get_subfields("a"))


def is_iso6393_field(field: Field) -> bool:
    """
    set 2: ISO 639-3
    Criteria: 041$a with a code from ISO 639-3. This will be indicated by a 2nd ind = 7 and $2 iso639-3.

    Example: 041 07 $a fra $a gsl $2 iso639-3 (Used to show the record includes French and a specific, less common language identified via ISO 639-3)

    """
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

    # set 1: ISO 639-5
    # TODO: I can create a function for each set
    code_008 = extract_008_language_code(record)

    if code_008 and code_008 in iso6395_codes:
        matched_codes.append(code_008)
        matched_set_types.append("iso639-5")
        set1_matched = True

    for field in record.get_fields("041"):
        field_codes = get_041_codes(field)

        # Check if the language code match with the list of codes given as input
        iso6395_matches = [code for code in field_codes if code in iso6395_codes]

        # Add all the languages that appear in the record.
        if iso6395_matches:
            matched_codes.extend(iso6395_matches)
            matched_set_types.append("iso639-5")
            relevant_041_fields.append(field)
            set1_matched = True

        # set 2: ISO 639-3
        if is_iso6393_field(field) and field_codes:
            matched_codes.extend(field_codes)
            matched_set_types.append("iso639-3")
            relevant_041_fields.append(field)  # e.g. [=041  \7$adeu$aeng$afra$2iso639-3]

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
    # Iterate for each record
    for record in iter_marc_records(path):
        # Look for the record that meet the input criteria
        row = match_record(record, iso6395_codes)
        if row is not None:
            yield row


def write_metadata_document(
    metadata_file: Path,
    *,
    input_file: Path,
    output_file: Path,
    iso6395_file: Path,
    written_rows: int,
) -> Path:
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_file": str(input_file),
        "output_file": str(output_file),
        "iso6395_file": str(iso6395_file),
        "written_rows": written_rows,
        "column_order": OUTPUT_COLUMNS,
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
    }
    metadata_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return metadata_file


def main() -> None:
    args = parse_args()
    logger.info("Reading Zephir export from %s", args.input_file)

    iso6395_codes = load_iso6395_codes(args.iso6395_file)
    rows_path, written_rows = write_tsv(
        generate_relevant_rows(args.input_file, iso6395_codes),
        args.output_file,
        columns_name=OUTPUT_COLUMNS,
    )

    metadata_summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_file": str(args.input_file),
        "output_file": str(rows_path),
        "iso6395_file": str(args.iso6395_file),
        "written_rows": written_rows,
        "column_order": OUTPUT_COLUMNS,
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
    }

    write_metadata_summary(args.metadata_file, metadata_summary)

    logger.info("Generated %d language-report rows at %s", written_rows, rows_path)


if __name__ == "__main__":
    main()
