"""CLI and helpers for generating dissertation metadata lists from Zephir MARC exports."""

import argparse
import csv
import gzip
import json
import re

from datetime import datetime, UTC
from pathlib import Path
from typing import Iterable, Iterator, Sequence
from pymarc import Record

from ht_utils.ht_marc_json_reader import MarcJsonReader, dict_to_pymarc_record
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

DEFAULT_KEYWORDS = ("dissertation", "phd", "ph.d.", "doctoral", "degree of doctor")
KEYWORD_FIELDS = ("245", "502", "653", "655", "650", "651", "500", "533")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract dissertation metadata from Zephir MARC JSON.")
    parser.add_argument(
        "--input-file",
        "-i",
        type=Path,
        default=Path(__file__).parent / "data" / "zephir_full_20260331_vufind.json.gz",
        help="Path to the Zephir MARC JSON export (gzipped).",
    )
    parser.add_argument(
        "--output-file",
        "-o",
        type=Path,
        default=Path(__file__).parent / "output" / "dissertation_metadata.csv",
        help="CSV file where dissertation metadata will be written.",
    )
    parser.add_argument(
        "--metadata-file",
        "-m",
        type=Path,
        default=Path(__file__).parent / "output" / "dissertation_metadata_query.json",
        help="Metadata document describing the filters used.",
    )
    return parser.parse_args()


def iter_marc_records(path: Path) -> Iterator[Record]:
    """
    The Zephir export is newline-delimited JSON with one MARC record per line, gzipped.
    This function reads the gz file line by line via the helper class MarcJsonReader and iterates over MARC records
    from a Zephir MARC JSON export.
    MarcJsonReader already strips blank lines, skips malformed JSON, and yields one Record per line.
    """
    if not path.exists():
        raise FileNotFoundError(f"Cannot find Zephir export at {path}")
    # MarcJsonReader expects a text file-like object, so we open the gzipped file in text mode (rt) with UTF-8 encoding.
    with gzip.open(path, "rt", encoding="utf-8", errors="ignore") as fh:

        for record in MarcJsonReader(fh):
            if record is None:
                logger.warning("Skipped malformed MARC JSON record while iterating %s", path)
                continue
            yield dict_to_pymarc_record(record)

def keyword_text(record: Record) -> str:

    """
    Generate keyword text from a Record.

    This function compiles a list of text fields from the given record,
    combining its title and formatted text content of specific fields. The
    result is a single lowercase string, with text segments joined by a
    space character.

    Parameters:
    record (Record): The Record object from which the keyword text is
    generated.

    Returns:
    str: A single lowercase string composed of the record's title and
    formatted fields.
    """

    texts: list[str] = []
    title = record.title
    if title:
        texts.append(title)
    for field in record.get_fields(*KEYWORD_FIELDS):
        texts.append(field.format_field())
    return " ".join(texts).lower()


def record_matches(record: Record, keywords: Sequence[str]) -> bool:
    text = keyword_text(record)
    return any(keyword.lower() in text for keyword in keywords)


def extract_identifiers(record: Record) -> list[str]:

    """
    Extract identifiers from a Zephir MARC JSON record.

    Parameters:
        record: MARC record object
    Returns
        List of identifiers extracted from the Zephir MARC JSON record.
    """

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

    """
    It retrieves subjects from the MARC record by looking at specific fields (650, 651, 655, 653)
    instead of using the built-in pymarc helper record.subjects to remove duplicates and focus
    on relevant subject fields.

    Parameters:
        record: MARC record object

    Returns:
        List of subject strings extracted from the record's subject fields.
    """

    #subjects: list[str] = []
    #for field in getattr(record, "subjects", []):
    #    subjects.extend(field.get_subfields("a"))
    #return [subject.strip() for subject in subjects if subject and subject.strip()]

    subjects: list[str] = []
    for tag in ("650", "651", "655", "653"):
        for field in record.get_fields(tag):
            subjects.extend(field.get_subfields("a"))
    return [subject.strip() for subject in subjects if subject and subject.strip()]

def extract_control_number(record: Record) -> str:
    """
    Extracts the unique identifier assigned to the MARC record.

    Parameters:
    record (Record): The record object from which the control number is extracted.

    Returns:
    str: The extracted control number as a string, or an empty string if the field
    is not present.
    """
    field = record.get_fields("001")
    if field:
        return field[0].value()
    return ""


def extract_publication_year(record: Record) -> str:
    """
    Extracts the publication year from the MARC record using the field pubyear if available by pymarc,
     or by searching for a 4-digit year in the subfields of fields 264 and 260.
    Parameters:
        record (Record): The record object from which the publication year is extracted.
    Returns:
        str: The extracted publication year as a string, or an empty string if the field
    """

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
    subjects = collect_subjects(record)
    other_sources = extract_identifiers(record)

    return {
        "control_number": extract_control_number(record),
        "title": record.title or "",
        "author": record.author or "",
        "year_published": extract_publication_year(record),
        "discipline": "; ".join(subjects),
        "other_sources": "; ".join(other_sources)
    }


def generate_dissertation_rows(path: Path, keywords: Sequence[str] = DEFAULT_KEYWORDS) -> Iterable[dict[str, str]]:
    for record in iter_marc_records(path):
        if record_matches(record, keywords):
            yield build_metadata_row(record)


def write_csv(rows: Iterable[dict[str, str]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["control_number", "title", "author", "year_published", "discipline", "other_sources"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        written = False
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
            written = True
    if not written:
        logger.warning("No dissertation rows were written to %s", path)
    return path


def write_metadata_document(query_file: Path, input_file: Path, output_file: Path, keywords: Sequence[str]) -> Path:
    query_file.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_file": str(input_file),
        "output_file": str(output_file),
        "keywords": list(keywords),
        "marc fields": list(KEYWORD_FIELDS),
        "description": "Records whose MARC fields contain dissertation or PhD identifiers.",
    }
    query_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return query_file




def main() -> None:
    args = parse_args()
    logger.info("Reading Zephir export from %s", args.input_file)
    rows = list(generate_dissertation_rows(args.input_file))
    logger.info("Found %d dissertation records", len(rows))
    csv_path = write_csv(rows, args.output_file)
    write_metadata_document(args.metadata_file, args.input_file, csv_path, DEFAULT_KEYWORDS)
    logger.info("Generated metadata CSV at %s", csv_path)


if __name__ == "__main__":
    main()
