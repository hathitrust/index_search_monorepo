"""Generate a KBART TSV from a holdings report keyed by catalog_id."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import multiprocessing
import os
from collections.abc import Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_mysql import HtMysql, get_mysql_conn
from ht_utils.ht_utils import (
    get_solr_url,
    normalize_catalog_id_pad_zeros,
    normalize_catalog_id_stripped_zeros,
    split_into_batches,
    write_metadata_summary,
    write_tsv,
)
from ht_utils.query_maker import make_solr_term_query
from ht_utils.text_processor import first_value, list_values

logger = get_ht_logger(name=__name__)

KBART_COLUMN_ORDER = [
    "publication_title",
    "print_identifier",
    "online_identifier",
    "date_first_issue_online",
    "num_first_vol_online",
    "num_first_issue_online",
    "date_last_issue_online",
    "num_last_vol_online",
    "num_last_issue_online",
    "title_url",
    "first author",
    "title_id",
    "embargo_info",
    "coverage_depth",
    "coverage_notes",
    "publisher_name",
    "oclc_number",
]

MAX_WORKERS = 20

DEFAULT_INPUT_FILE = Path(__file__).parent / "data" / "data"
DEFAULT_OUTPUT_FILE = Path(__file__).parent / "output" / "kbart_print_holdings.tsv"
DEFAULT_METADATA_FILE = Path(__file__).parent / "output" / "kbart_print_holdings.metadata.json"
DEFAULT_ERROR_FILE = Path(__file__).parent / "output" / "kbart_print_holdings.errors.tsv"
DEFAULT_BATCH_SIZE = 100

SOLR_FIELDS = [
    "id",
    "title_display",
    "isbn",
    "issn",
    "mainauthor",
    "publisher",
    "oclc",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a KBART TSV from a holdings report.")
    parser.add_argument(
        "--input-file", "-f", type=Path, default=DEFAULT_INPUT_FILE, help="Input holdings TSV path."
    )
    parser.add_argument(
        "--output-file", "-o", type=Path, default=DEFAULT_OUTPUT_FILE, help="Output KBART TSV path."
    )
    parser.add_argument(
        "--metadata-file",
        "-m",
        type=Path,
        default=DEFAULT_METADATA_FILE,
        help="JSON summary sidecar path.",
    )
    parser.add_argument(
        "--error-file",
        "-e",
        type=Path,
        default=DEFAULT_ERROR_FILE,
        help="TSV error sidecar path.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Maximum number of catalog_ids to include per Solr request.",
    )
    parser.add_argument(
        "--env", default=os.environ.get("HT_ENVIRONMENT", "dev"), help="Lookup environment."
    )
    parser.add_argument(
        "--solr-url",
        default=os.environ.get("SOLR_URL"),
        help="Override Solr base URL, e.g. http://localhost:8983/solr/catalog.",
    )
    return parser.parse_args()


def read_catalog_ids(path: Path) -> list[str]:

    if not path.exists():
        raise FileNotFoundError(f"Cannot find holdings report at {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None or "catalog_id" not in reader.fieldnames:
            raise ValueError(f"Holdings report {path} is missing required column 'catalog_id'")

        ordered_catalog_ids: dict[str, None] = {}
        for row in reader:
            catalog_id = (row.get("catalog_id") or "").strip()
            if catalog_id:
                ordered_catalog_ids.setdefault(catalog_id, None)
    return list(ordered_catalog_ids)


def filter_out_dates(value: str) -> str:
    """
    date_first_issue_online and date_last_issue_online, are not populate if the value
    is 9999 or if the value is less than 4 digits.
    """

    if value is None or value == str(9999) or len(value) < 4:
        return ""
    else:
        return value


def check_bib_fmt_field(title_dates: Mapping[str, object]) -> str:

    if first_value((title_dates or {}).get("bib_fmt")) != "SE":
        return ""
    else:
        return filter_out_dates(first_value((title_dates or {}).get("date_last_issue_online")))


def build_kbart_row(
    metadata: Mapping[str, object],
    title_dates: Mapping[str, object] | None = None,
) -> dict[str, str]:
    raw_id = first_value(metadata.get("id"))
    title_id = normalize_catalog_id_stripped_zeros(raw_id)
    identifiers = list_values(metadata.get("isbn")) or list_values(metadata.get("issn"))
    # solr field value: publisher
    publisher_name = first_value(metadata.get("publisher"))
    # first value present in solr field oclc
    oclc_number = first_value(metadata.get("oclc"))

    return {
        # value of solr field: title_display
        "publication_title": first_value(metadata.get("title_display")),
        # value of solr isbn or issn.  Where multiple values, select only first value
        "print_identifier": first_value(identifiers),
        "online_identifier": "",
        "date_first_issue_online": filter_out_dates(
            first_value((title_dates or {}).get("date_first_issue_online"))
        ),
        "num_first_vol_online": "",
        "num_first_issue_online": "",
        "date_last_issue_online": check_bib_fmt_field(title_dates),
        "num_last_vol_online": "",
        "num_last_issue_online": "",
        "title_url": f"https://catalog.hathitrust.org/Record/{title_id}",
        "first author": first_value(metadata.get("mainauthor")),
        "title_id": title_id,
        "embargo_info": "",
        "coverage_depth": "",
        "coverage_notes": "",
        "publisher_name": publisher_name,
        "oclc_number": oclc_number,
    }


def fetch_title_dates_from_mysql_batch(
    batch: Sequence[str],
    db_conn: HtMysql,
) -> dict[str, dict[str, object]]:
    if not batch:
        return {}

    bind_names = [f"bib_num_{index}" for index, _ in enumerate(batch)]
    params = {bind_name: bib_num for bind_name, bib_num in zip(bind_names, batch, strict=False)}
    placeholders = ", ".join(f":{bind_name}" for bind_name in bind_names)
    query = f"""
        SELECT
            bib_num, bib_fmt,
            MIN(rights_date_used) AS date_first_issue_online,
            MAX(rights_date_used) AS date_last_issue_online
        FROM hf
        WHERE bib_num IN ({placeholders})
        GROUP BY bib_num
    """

    results_by_id: dict[str, dict[str, object]] = {}
    for row in db_conn.query_mysql(query, params=params):
        bib_num = first_value(row.get("bib_num"))
        if bib_num:
            results_by_id[bib_num] = row

    return results_by_id


def fetch_title_metadata_from_solr_batch(
    batch: Sequence[str],
) -> dict[str, dict[str, object]]:
    if not batch:
        return {}

    query_url = f"{get_solr_url()}/query"
    params = {
        "q": "*:*",
        "fl": ",".join(SOLR_FIELDS),
        "rows": len(batch),
        "wt": "json",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if os.getenv("SOLR_USER") and os.getenv("SOLR_PASSWORD"):
        raw_auth = f"{os.environ['SOLR_USER']}:{os.environ['SOLR_PASSWORD']}".encode()
        headers["Authorization"] = f"Basic {base64.b64encode(raw_auth).decode('ascii')}"

    normalized_batch = [normalize_catalog_id_pad_zeros(catalog_id) for catalog_id in batch]

    params.update({"fq": make_solr_term_query(normalized_batch, "record")})
    request = Request(
        query_url,
        data=urlencode(params).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(
            f"Solr query failed with HTTP {exc.code} for batch {list(batch)}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Solr at {query_url}") from exc

    results_by_id: dict[str, dict[str, object]] = {}
    docs = payload.get("response", {}).get("docs", [])
    for document in docs:
        if isinstance(document, dict):
            document_id = first_value(document.get("id"))
            if document_id:
                results_by_id[normalize_catalog_id_stripped_zeros(document_id)] = document
    return results_by_id


def fetch_lookup_results_in_parallel(
    catalog_ids: Sequence[str],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    if not catalog_ids:
        return {}, {}

    id_batches = list(split_into_batches(list(catalog_ids), batch_size))
    total_workers = min(multiprocessing.cpu_count() * 2, MAX_WORKERS)

    db_conn = get_mysql_conn(pool_size=total_workers)

    metadata_by_id: dict[str, dict[str, object]] = {}
    date_by_id: dict[str, dict[str, object]] = {}

    with ThreadPoolExecutor(max_workers=total_workers) as executor:
        future_to_source: dict[Future[Mapping[str, Mapping[str, object]]], str] = {}
        for batch in id_batches:
            logger.info("Processing batch: %s", len(batch))
            future_to_source[executor.submit(fetch_title_metadata_from_solr_batch, batch)] = "solr"
            future_to_source[
                executor.submit(fetch_title_dates_from_mysql_batch, batch, db_conn)
            ] = "mysql"

        try:
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                batch_results = {key: dict(value) for key, value in future.result().items()}
                if source == "solr":
                    metadata_by_id.update(batch_results)
                else:
                    date_by_id.update(batch_results)
        except Exception:
            for pending_future in future_to_source:
                pending_future.cancel()
            raise

    logger.info(
        "Parallel process: Extracted %d metadata from Solr and %d metadata from MySQL",
        len(metadata_by_id),
        len(date_by_id),
    )

    return metadata_by_id, date_by_id


def write_error_report(path: Path, errors: Sequence[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["catalog_id", "reason"], delimiter="\t")
        writer.writeheader()
        for error in errors:
            writer.writerow(
                {"catalog_id": error.get("catalog_id", ""), "reason": error.get("reason", "")}
            )
    return path


def generate_kbart_rows(
    catalog_ids: Sequence[str],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    metadata_by_id, date_by_id = fetch_lookup_results_in_parallel(
        catalog_ids, batch_size=batch_size
    )

    logger.info(
        "Extracted %d metadata from Solr and %d metadata from MySQL",
        len(metadata_by_id),
        len(date_by_id),
    )

    rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    for catalog_id in catalog_ids:
        metadata = metadata_by_id.get(catalog_id)
        if metadata is None:
            errors.append({"catalog_id": catalog_id, "reason": "metadata not found"})
            continue

        row = build_kbart_row(metadata, date_by_id.get(catalog_id))
        if not row["publication_title"] or not row["title_id"]:
            errors.append({"catalog_id": catalog_id, "reason": "required source fields missing"})
            continue
        rows.append(row)

    return rows, errors


def generate_kbart_export(
    input_file: Path,
    output_file: Path,
    metadata_file: Path,
    error_file: Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[int, list[dict[str, str]]]:
    # Load all the rows of the file
    catalog_ids = read_catalog_ids(input_file)
    rows, errors = generate_kbart_rows(
        catalog_ids,
        batch_size=batch_size,
    )

    rows_path, written_rows = write_tsv(rows, output_file, columns_name=KBART_COLUMN_ORDER)
    write_error_report(error_file, errors)

    metadata_summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_file": str(input_file),
        "output_file": str(output_file),
        "error_file": str(error_file),
        "processed_catalog_ids": len(catalog_ids),
        "written_rows": written_rows,
        "skipped_rows": len(errors),
        "column_order": KBART_COLUMN_ORDER,
    }

    write_metadata_summary(metadata_file, metadata_summary)
    return len(rows), errors


def main() -> None:
    args = parse_args()
    logger.info("Reading KBART holdings report from %s", args.input_file)
    written_rows, errors = generate_kbart_export(
        args.input_file,
        args.output_file,
        args.metadata_file,
        args.error_file,
        batch_size=args.batch_size,
    )
    logger.info("Generated %d KBART rows", written_rows)
    if errors:
        logger.warning("Skipped %d catalog_ids during KBART generation", len(errors))


if __name__ == "__main__":
    main()
