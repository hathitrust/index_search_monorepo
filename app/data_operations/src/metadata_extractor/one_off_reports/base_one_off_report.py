import csv
from abc import abstractmethod, ABC
from dataclasses import dataclass
from collections.abc import Sequence
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Mapping, Iterable
from metadata_extractor.one_off_reports.ht_marc_json_reader import iter_marc_records

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

@dataclass(frozen=True)
class BaseOneOffReport(ABC):
    default_input_file: Path
    default_output_file: Path
    default_metadata_file: Path
    output_columns: Sequence[str]
    output_file_format: str

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

    def write_csv(self, rows: Iterable[dict[str, str]], path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=self.output_columns)
            writer.writeheader()
            written = False
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in self.output_columns})
                written = True
        if not written:
            logger.warning("No dissertation rows were written to %s", path)
        return path

    @abstractmethod
    def match_record(self, record):
        pass

    def generate_relevant_rows(self, path: Path, iso6395_codes: set[str]) -> Iterable[dict[str, str]]:
        # Iterate for each record
        for record in iter_marc_records(path):
            # Look for the record that meet the input criteria
            # Each subclass will implement the match_record method to return a dictionary of the relevant fields for the report
            row = self.match_record(record)
            if row is not None:
                yield row
