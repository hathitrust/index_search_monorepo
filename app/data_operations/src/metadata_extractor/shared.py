"""Shared scaffolding and MARC helpers for one-off metadata reports."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ht_utils.ht_utils import write_metadata_summary as write_metadata_summary_file
from pymarc import Field, Record


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    ordered: dict[str, None] = {}
    for value in values:
        cleaned = value.strip()
        if cleaned:
            ordered.setdefault(cleaned, None)
    return list(ordered)


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
    field_008 = record.get_fields("008")
    if not field_008:
        return ""
    value = field_008[0].value()
    if not value or len(value) < 38:
        return ""
    return value[35:38].strip().lower()


def extract_041_language_codes(field: Field) -> list[str]:
    return unique_preserve_order(value.strip().lower() for value in field.get_subfields("a"))


@dataclass(frozen=True)
class BaseOneOffReport:
    default_input_file: Path
    default_output_file: Path
    default_metadata_file: Path
    output_columns: Sequence[str]

    def build_base_metadata_summary(
        self,
        *,
        input_file: Path,
        output_file: Path,
        written_rows: int,
        extra_metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "generated_at": datetime.now(UTC).isoformat(),
            "input_file": str(input_file),
            "output_file": str(output_file),
            "written_rows": written_rows,
        }
        if self.output_columns:
            payload["column_order"] = list(self.output_columns)
        if extra_metadata:
            payload.update(dict(extra_metadata))
        return payload

    def write_metadata_summary(self, metadata_file: Path, summary: Mapping[str, Any]) -> Path:
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        write_metadata_summary_file(metadata_file, dict(summary))
        return metadata_file
