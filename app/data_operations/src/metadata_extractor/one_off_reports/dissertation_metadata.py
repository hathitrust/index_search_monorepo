"""Generate dissertation metadata from Zephir MARC exports."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_marc_json_reader import extract_control_number, iter_marc_records
from pymarc import Record

if TYPE_CHECKING:
    from ..shared import BaseOneOffReport
else:
    if __package__ in {None, ""}:
        sys.path.append(str(Path(__file__).resolve().parents[2]))
    from metadata_extractor.shared import BaseOneOffReport

logger = get_ht_logger(name=__name__)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KEYWORDS = ("dissertation", "phd", "ph.d.", "doctoral", "degree of doctor")
KEYWORD_FIELDS = ("502", "653", "655", "650", "651", "500", "533")
OUTPUT_COLUMNS = [
    "control_number",
    "title",
    "author",
    "year_published",
    "discipline",
    "other_sources",
]


class DissertationMetadataReport(BaseOneOffReport):
    def __init__(self) -> None:
        super().__init__(
            default_input_file=PACKAGE_ROOT / "data" / "zephir_full_20260331_vufind.json.gz",
            default_output_file=PACKAGE_ROOT / "output" / "full_dissertation_metadata_MUI.csv",
            default_metadata_file=PACKAGE_ROOT / "output" / "dissertation_metadata_query.json",
            output_columns=OUTPUT_COLUMNS,
        )

    def build_metadata_summary(
        self,
        *,
        input_file: Path,
        output_file: Path,
        written_rows: int,
        institution_id: str,
        keywords: Sequence[str],
    ) -> dict[str, Any]:
        return self.build_base_metadata_summary(
            input_file=input_file,
            output_file=output_file,
            written_rows=written_rows,
            extra_metadata={
                "keywords": list(keywords),
                "marc_fields": list(KEYWORD_FIELDS),
                "marc_fields_institution": "974$b",
                "institution_id": institution_id,
                "description": "Records whose MARC fields contain dissertation or PhD identifiers.",
            },
        )


REPORT = DissertationMetadataReport()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract dissertation metadata from Zephir MARC JSON."
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
        help="CSV file where dissertation metadata will be written.",
    )
    parser.add_argument(
        "--metadata-file",
        "-m",
        type=Path,
        default=REPORT.default_metadata_file,
        help="Metadata document describing the filters used.",
    )
    parser.add_argument(
        "--institution_id",
        "-i",
        type=str,
        default="MIU",
        help="The institution identifier to filter records by (e.g., 'MIU' for University of Michigan). Records will be included if they have this identifier in the 974$b subfield.",
    )
    return parser.parse_args()


def keyword_text(record: Record) -> str:
    texts: list[str] = []
    for field in record.get_fields(*KEYWORD_FIELDS):
        texts.append(field.format_field())
    return " ".join(texts).lower()


def get_specific_institution_records(record: Record, institution_id: str = "MIU") -> bool:
    normalized_institution_id = institution_id.strip().casefold()
    for field in record.get_fields("974"):
        for sub in field.get_subfields("b"):
            if normalized_institution_id == sub.strip().casefold():
                return True
    return False


def record_matches(record: Record, keywords: Sequence[str]) -> bool:
    text = keyword_text(record)
    for keyword in keywords:
        if keyword.lower() in text:
            return True
    return any(keyword.lower() in text for keyword in keywords)


def extract_identifiers(record: Record) -> list[str]:
    identifiers: list[str] = []
    for field in record.get_fields("502"):
        for sub in field.get_subfields("o"):
            if sub:
                identifiers.append(sub.strip())
    for field in record.get_fields("035"):
        for code in ("a", "z"):
            for sub in field.get_subfields(code):
                if sub:
                    identifiers.append(sub.strip())
    return identifiers


def collect_subjects(record: Record) -> list[str]:
    subjects: list[str] = []
    for tag in ("650", "651", "655", "653"):
        for field in record.get_fields(tag):
            subjects.extend(field.get_subfields("a"))
    return [subject.strip() for subject in subjects if subject and subject.strip()]


def extract_publication_year(record: Record) -> str:
    pubyear_attr = getattr(record, "pubyear", None)
    if callable(pubyear_attr):
        try:
            year = pubyear_attr()
            if year:
                match = re.search(r"\d{4}", year)
                if match:
                    return match.group(0)
        except Exception:
            pass
    for tag in ("264", "260"):
        for field in record.get_fields(tag):
            for csub in field.get_subfields("c"):
                match = re.search(r"\d{4}", csub or "")
                if match:
                    return match.group(0)
    return ""


def build_metadata_row(record: Record) -> dict[str, str]:
    return {
        "control_number": extract_control_number(record),
        "title": record.title or "",
        "author": record.author or "",
        "year_published": extract_publication_year(record),
        "discipline": "; ".join(collect_subjects(record)),
        "other_sources": "; ".join(extract_identifiers(record)),
    }


def generate_dissertation_rows(
    path: Path, keywords: Sequence[str] = DEFAULT_KEYWORDS, institution_id: str = "MIU"
) -> Iterable[dict[str, str]]:
    for record in iter_marc_records(path):
        if record_matches(record, keywords) and get_specific_institution_records(
            record, institution_id
        ):
            yield build_metadata_row(record)


def write_csv(rows: Iterable[dict[str, str]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        written = False
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in OUTPUT_COLUMNS})
            written = True
    if not written:
        logger.warning("No dissertation rows were written to %s", path)
    return path


def main() -> None:
    args = parse_args()
    logger.info("Reading Zephir export from %s", args.input_file)
    rows = list(generate_dissertation_rows(args.input_file, institution_id=args.institution_id))
    logger.info("Found %d dissertation records", len(rows))
    csv_path = write_csv(rows, args.output_file)
    metadata_summary = REPORT.build_metadata_summary(
        input_file=args.input_file,
        output_file=csv_path,
        written_rows=len(rows),
        institution_id=args.institution_id,
        keywords=DEFAULT_KEYWORDS,
    )
    REPORT.write_metadata_summary(args.metadata_file, metadata_summary)
    logger.info("Generated metadata CSV at %s", csv_path)


if __name__ == "__main__":
    main()
