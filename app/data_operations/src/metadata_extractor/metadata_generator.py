"""Compatibility wrapper for the renamed dissertation one-off report."""

from .one_off_reports.dissertation_metadata import (
    DEFAULT_KEYWORDS,
    KEYWORD_FIELDS,
    OUTPUT_COLUMNS,
    DissertationMetadataReport,
    build_metadata_row,
    collect_subjects,
    extract_identifiers,
    extract_publication_year,
    generate_dissertation_rows,
    get_specific_institution_records,
    keyword_text,
    main,
    parse_args,
    record_matches,
    write_csv,
)

__all__ = [
    "DEFAULT_KEYWORDS",
    "KEYWORD_FIELDS",
    "OUTPUT_COLUMNS",
    "DissertationMetadataReport",
    "build_metadata_row",
    "collect_subjects",
    "extract_identifiers",
    "extract_publication_year",
    "generate_dissertation_rows",
    "get_specific_institution_records",
    "keyword_text",
    "main",
    "parse_args",
    "record_matches",
    "write_csv",
]


if __name__ == "__main__":
    main()
