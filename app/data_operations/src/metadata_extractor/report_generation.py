"""Compatibility wrapper for the renamed ISO 041 language report."""

from .one_off_reports.extract_041_language_codes import (
    DEFAULT_ISO6395_FILE,
    ISO6393_SOURCE,
    OUTPUT_COLUMNS,
    RIGHTS_CODES,
    Extract041LanguageCodesReport,
    build_report_row,
    extract_rights_code,
    format_fields,
    generate_relevant_rows,
    is_iso6393_field,
    load_iso6395_codes,
    main,
    match_record,
    parse_args,
)

__all__ = [
    "DEFAULT_ISO6395_FILE",
    "ISO6393_SOURCE",
    "OUTPUT_COLUMNS",
    "RIGHTS_CODES",
    "Extract041LanguageCodesReport",
    "build_report_row",
    "extract_rights_code",
    "format_fields",
    "generate_relevant_rows",
    "is_iso6393_field",
    "load_iso6395_codes",
    "main",
    "match_record",
    "parse_args",
]


if __name__ == "__main__":
    main()
