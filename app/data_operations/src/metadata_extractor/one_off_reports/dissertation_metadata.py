import argparse
from dataclasses import dataclass
from pathlib import Path

from metadata_extractor.one_off_reports.base_one_off_report import BaseOneOffReport
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import write_metadata_summary

logger = get_ht_logger(name=__name__)

# Parameter to define the folder to load the results
PACKAGE_ROOT = Path(__file__).resolve().parent.parent

# Metadata to show in the generated report
OUTPUT_COLUMNS = [
    "control_number",
    "title",
    "author",
    "year_published",
    "discipline",
    "other_sources",
]

# TODO: How can we generalize the search criteria?
DEFAULT_KEYWORDS = ("dissertation", "phd", "ph.d.", "doctoral", "degree of doctor")
KEYWORD_FIELDS = ("502", "653", "655", "650", "651", "500", "533")

@dataclass(frozen=True)
class DissertationMetadata(BaseOneOffReport):
    institution_id = None

    def __init__(self) -> None:
        super().__init__(
            default_input_file=PACKAGE_ROOT / "data" / "zephir_full_20260331_vufind.json.gz",
            default_output_file=PACKAGE_ROOT / "output" / "full_dissertation_metadata_MUI.csv",
            default_metadata_file=PACKAGE_ROOT / "output" / "dissertation_metadata_query.json",
            output_columns=OUTPUT_COLUMNS,
            output_file_format="csv",
        )

    # Abstract method to implement by the child class
    def record_matches(self, record: Record, keywords: Sequence[str]) -> bool:
        text = keyword_text(record)
        for keyword in keywords:
            if keyword.lower() in text:
                return True
        return any(keyword.lower() in text for keyword in keywords)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract dissertation metadata from Zephir MARC JSON."
    )
    parser.add_argument(
        "--input-file",
        "-f",
        type=Path,
        default=PACKAGE_ROOT / "data" / "zephir_full_20260331_vufind.json.gz",
        help="Path to the Zephir MARC JSON export (gzipped).",
    )
    parser.add_argument(
        "--output-file",
        "-o",
        type=Path,
        default=PACKAGE_ROOT / "output" / "full_dissertation_metadata_MUI.csv",
        help="CSV file where dissertation metadata will be written.",
    )
    parser.add_argument(
        "--metadata-file",
        "-m",
        type=Path,
        default=PACKAGE_ROOT / "output" / "dissertation_metadata_query.json",
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

def main() -> None:
    args = parse_args()
    logger.info("Reading Zephir export from %s", args.input_file)

    list_rows = []
    dissertation_metadata = DissertationMetadata()
    for row in dissertation_metadata.generate_relevant_rows(args.input_file):
        if dissertation_metadata.record_matches(row, KEYWORD_FIELDS):
            list_rows.append(row)

    logger.info("Found %d dissertation records", len(list_rows))
    csv_path = dissertation_metadata.write_csv(list_rows, args.output_file)

    #metadata_summary = {
    #    "generated_at": datetime.now(UTC).isoformat(),
    #    "input_file": str(args.input_file),
    #    "output_file": str(csv_path),
    #    "keywords": list(DEFAULT_KEYWORDS),
    #    "marc fields": list(KEYWORD_FIELDS),
    #    "marc fields institution": "974$b",
    #    "description": "Records whose MARC fields contain dissertation or PhD identifiers.",
    #}

    metadata_summary = dissertation_metadata.build_base_metadata_summary(
        input_file=args.input_file,
        output_file=csv_path,
        written_rows=len(list_rows),
        extra_metadata= {
            "marc fields": list(KEYWORD_FIELDS),
            "institution_id": args.institution_id,
            "marc fields institution": "974$b",
            "description": "Records whose MARC fields contain dissertation or PhD identifiers."
        }
    )

    write_metadata_summary(args.metadata_file, metadata_summary)
    logger.info("Generated metadata CSV at %s", csv_path)


if __name__ == "__main__":
    main()