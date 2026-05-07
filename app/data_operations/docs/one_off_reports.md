# One-off Metadata Reports

This document describes how `app/data_operations` organizes one-off reports under
`src/metadata_extractor`, which parts are intended for reuse, and how to document
the request that caused a report to exist.

## Package layout

One-off metadata reports live in:

    app/data_operations/src/metadata_extractor/one_off_reports/

Shared report scaffolding and reusable MARC helpers live in:

    app/data_operations/src/metadata_extractor/shared.py

The shared layer is intentionally small. It is the right home for:

- metadata-sidecar construction and writing
- default input/output path ownership for report classes
- generic MARC helpers that are likely to help future reports

The shared layer is not the right home for:

- report-specific CLI flags
- report-specific code lists
- matching rules that only make sense for one request

When a helper is only meaningful for one report, keep it in that report module even
if the function is short.

## Reusable scaffolding

`metadata_extractor.shared` currently provides:

- `BaseOneOffReport` for default file paths plus metadata-sidecar writing
- `unique_preserve_order(...)`
- `extract_oclc_number(...)`
- `extract_008_language_code(...)`
- `extract_041_language_codes(...)`

Future one-off reports should reuse these pieces when they fit. Do not extend the
base class with report-specific filters or extra CLI flags.

## Existing reports

### Dissertation metadata report

- Module: `src/metadata_extractor/one_off_reports/dissertation_metadata.py`
- Purpose: generate a CSV of dissertation-like titles from a Zephir MARC export
- Shared pieces reused: metadata-sidecar writing through `BaseOneOffReport`
- Report-specific pieces kept local: dissertation keyword matching, institution
  filtering, identifier extraction, and row-shape decisions
- Originating request reference: `issues/close/phase1_dissertation_metadata.md`
- Original JIRA/request id: unknown from repository history

Run it locally from `app/data_operations`:

```bash
uv run python src/metadata_extractor/one_off_reports/dissertation_metadata.py \
  --input-file src/metadata_extractor/data/zephir_upd_20260404.json.gz \
  --output-file src/metadata_extractor/output/full_dissertation_metadata_MUI.csv \
  --metadata-file src/metadata_extractor/output/dissertation_metadata_query.json \
  --institution_id MIU
```

### ISO 041 language report

- Module: `src/metadata_extractor/one_off_reports/extract_041_language_codes.py`
- Purpose: generate a TSV for titles matching the ISO 639-5 or ISO 639-3 language
  criteria from a Zephir MARC export
- Shared pieces reused: metadata-sidecar writing plus shared OCLC/008/041 helpers
- Report-specific pieces kept local: `--iso6395-file`, `load_iso6395_codes(...)`,
  rights filtering, and the `041` indicator / `$2 iso639-3` rule
- Originating request reference: `issues/close/draft-feature-iso639-language-report.md`
- Original JIRA/request id: unknown from repository history

Run it locally from `app/data_operations`:

```bash
uv run python src/metadata_extractor/one_off_reports/extract_041_language_codes.py \
  --input-file src/metadata_extractor/data/zephir_full_20260430_vufind.json.gz \
  --output-file src/metadata_extractor/output/iso639_language_report.tsv \
  --metadata-file src/metadata_extractor/output/iso639_language_report.metadata.json \
  --iso6395-file src/metadata_extractor/data/iso639-5.tsv
```

## Compatibility shims

The historical module paths:

- `src/metadata_extractor/metadata_generator.py`
- `src/metadata_extractor/report_generation.py`

remain as thin compatibility wrappers around the new one-off report modules. New
documentation and new code should use the explicit `one_off_reports` paths.

## How to document future one-off reports

Every new one-off report entry in this document should record:

- module path
- purpose in one sentence
- shared helpers/base classes reused
- report-specific logic intentionally kept local
- issue card or other repo reference
- JIRA ticket id or equivalent request artifact when known

If the original ticket or request id cannot be recovered, write `unknown from
repository history`. Do not guess.
