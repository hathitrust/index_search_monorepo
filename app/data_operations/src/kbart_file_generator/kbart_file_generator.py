"""Generate a KBART 3.0 TSV given an organization ID"""

from __future__ import annotations

import base64
import csv
import json
from collections.abc import Generator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import click
import regex
from ht_utils.ht_env_config import HtEnvConfig
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import (
    normalize_catalog_id_stripped_zeros,
    write_metadata_summary,
)
from ht_utils.text_processor import first_value, list_values

logger = get_ht_logger(name=__name__)

KBART_COLUMN_ORDER = [
    "publication_title",
    "alternate_publication_title",
    "alternate_title_type",
    "print_identifier",
    "online_identifier",
    "date_first_issue_online",
    "num_first_vol_online",
    "num_first_issue_online",
    "date_last_issue_online",
    "num_last_vol_online",
    "num_last_issue_online",
    "title_url",
    "contributor",
    "contributor_type",
    "title_id",
    "embargo_info",
    "coverage_depth",
    "notes",
    "publisher_name",
    "publication_type",
    "content_type",
    "date_monograph_published_print",
    "date_monograph_published_online",
    "monograph_volume",
    "monograph_edition",
    "duration",
    "parent_publication_title_id",
    "preceding_publication_title_id",
    "access_type",
    "oclc",
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
    "title",
    "vtitle",
    "isbn",
    "issn",
    "mainauthor",
    "publisher",
    "oclc",
    "display_date",
    "ht_id_display",
    "format",
    "edition",
]

@click.command()
@click.option("--inst-id", type=str, help="Institution ID to generate a report for.")
@click.option(
    "--output-file", "-o", type=Path, default=DEFAULT_OUTPUT_FILE, help="Output KBART TSV path."
)
@click.option(
    "--metadata-file",
    "-m",
    type=Path,
    default=DEFAULT_METADATA_FILE,
    help="JSON summary sidecar path.",
)
@click.option(
    "--error-file",
    "-e",
    type=Path,
    default=DEFAULT_ERROR_FILE,
    help="TSV error sidecar path.",
)
@click.option(
    "--batch-size",
    type=int,
    default=DEFAULT_BATCH_SIZE,
    help="Maximum number of rows to fetch per Solr request.",
)
def main(
    output_file: Path, metadata_file: Path, error_file: Path, batch_size: int, inst_id: str
) -> None:
    """Generate a KBART TSV from solr records for a given institution."""
    logger.info(f"Generating KBART report for {inst_id}")
    logger.info(f"Output to {output_file}")
    logger.info(f"Summary in {metadata_file}")
    logger.info(f"Errors in {error_file}")
    logger.info(f"Querying solr in batches of {batch_size}")
    row_count, error_count = generate_kbart_export(
        inst_id,
        output_file,
        metadata_file,
        error_file,
        batch_size=batch_size,
    )
    logger.info("Generated %d KBART rows", row_count)
    if error_count > 0:
        logger.warning("Skipped %d catalog_ids during KBART generation", error_count)


def filter_out_dates(value: str) -> str:
    """
    date_first_issue_online and date_last_issue_online, are not populate if the value
    is 9999 or if the value is less than 4 digits.
    """

    if value is None or value == str(9999) or len(value) < 4:
        return ""
    else:
        return value


def check_bib_fmt_field(title_dates: Mapping[str, object] | None) -> str:

    if first_value((title_dates or {}).get("bib_fmt")) != "SE":
        return ""
    else:
        return filter_out_dates(first_value((title_dates or {}).get("date_last_issue_online")))


def extract_dates(ht_id_display: Sequence[str]) -> tuple[str, str]:
    """returns the earliest & latest dates from the items in a record"""

    # data is an array of strings like
    # "uc1.b3753482|20260925|v.1 1937|1937|1930-1939|||Archives d'ophtalmologie et revue générale d'ophtalmologie, v.1 1937"
    # fields are pipe-separated; fields are:
    #
    # htid
    # last_update_date
    # enum_chron
    # enum_pubdate
    # enum_pubdate_range
    # title_sortkey
    # author_sortkey
    # dtitle
    #
    # we only care about enum_pubdate

    dates = [item_info.split("|")[3] for item_info in ht_id_display]
    return filter_out_dates(min(dates)), filter_out_dates(max(dates))


def build_kbart_row(
    metadata: Mapping[str, object],
) -> dict[str, str]:
    raw_id = first_value(metadata.get("id"))
    title_id = normalize_catalog_id_stripped_zeros(raw_id)
    identifiers = list_values(metadata.get("isbn")) or list_values(metadata.get("issn"))
    # remove trailing punctuation
    publisher_name = regex.sub(r"\p{Punctuation}*$", "", first_value(metadata.get("publisher")))
    oclc_number = first_value(metadata.get("oclc"))
    title_display = first_value(metadata.get("title_display"))
    title = first_value(metadata.get("title"))
    vtitle = first_value(metadata.get("vtitle"))
    mainauthor = (first_value(metadata.get("mainauthor")),)
    (min_date, max_date) = extract_dates(metadata.get("ht_id_display"))
    is_serial = "Serial" in metadata.get("format")
    is_monograph = "Book" in metadata.get("format")

    return {
        # value of solr field: title_display; if solr field 'vtitle' is present, only use field: title
        "publication_title": title if vtitle else title_display,
        # vtitle if present (or empty)
        "alternate_publication_title": vtitle,
        # when 'vtitle' field in solr, use value 'parallel'
        "alternate_title_type": "parallel" if vtitle else "",
        # value of solr isbn or issn.  Where multiple values, select only first value
        "print_identifier": first_value(identifiers),
        # null
        "online_identifier": "",
        # When we have year values, in the 974$y, especially for serials and MPMs, are we able to identify the earliest of those values? If so, use that value; if not, use solr display_date
        "date_first_issue_online": min_date,
        # null
        "num_first_vol_online": "",
        # null
        "num_first_issue_online": "",
        # Similar to date_first, if we are able to identify the most recent year value, use that. If not, leave blank
        "date_last_issue_online": max_date,
        # null
        "num_last_vol_online": "",
        # null
        "num_last_issue_online": "",
        # Use the solr value of id, stripped of leading 0s, to create a link to the title level record.
        "title_url": f"https://catalog.hathitrust.org/Record/{title_id}",
        # for monograph, use first value in solr field 'mainauthor'; for serials leave null
        "contributor": "" if is_serial else mainauthor,
        # if 'mainauthor' is present in sorl record, value is 'Author', otherwise null
        "contributor_type": "Author" if mainauthor and not is_serial else "",
        # use solr field id_int
        "title_id": title_id,
        # null
        "embargo_info": "",
        # always value 'full',
        "coverage_depth": "full",
        # value: "Access is variable and dependent on resource sharing participation"
        "note": "Access is variable and dependent on resource sharing participation",
        # solr field value: publisher, remove trailing punctuation
        "publisher_name": publisher_name,
        # from "format" in solr. Where value contains "serial" should be 'Serial'. Where contains "book" should be "monograph"
        "publication_type": "Serial" if is_serial else "Book" if is_monograph else "",
        # value is 'text'
        "content_type": "text",
        # When we have year values, in the 974$y, especially for serials and MPMs, are we able to identify the earliest of those values? If so, use that value; if not, use solr display_date
        "date_monograph_published_print": min_date,
        # null,
        "date_monograph_published_online": "",
        # null
        "monograph_volume": "",
        # from Edition field in solr
        "monograph_edition": first_value(metadata.get("edition")),
        # null
        "duration": "",
        # difficult to identify so 'null'
        "parent_publication_title_id": "",
        # null
        "preceding_publication_title_id": "",
        # hardcode as 'M' which means 'Mixed
        "access_type": "M",
        # first value present in solr field oclc
        "oclc": oclc_number,
    }


def matching_solr_records(inst_id: str, batch_size: int) -> Generator[dict[str, object]]:
    query_url = f"{HtEnvConfig().catalog_solr_ro_url.rstrip('/')}/query"
    last_cursor = None
    current_cursor = "*"
    params = {
        "q": "*:*",
        "sort": "id asc",
        "fq": f'print_holdings:{inst_id} OR ht_availability:"Full text"',
        "fl": ",".join(SOLR_FIELDS),
        "rows": batch_size,
        "wt": "json",
        "cursorMark": current_cursor
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    env_config = HtEnvConfig()
    raw_auth = f"{env_config.solr_user}:{env_config.solr_password}".encode()
    headers["Authorization"] = f"Basic {base64.b64encode(raw_auth).decode('ascii')}"

    while last_cursor != current_cursor:
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
            raise RuntimeError(f"Solr query failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Could not reach Solr at {query_url}") from exc

        response = payload.get("response", {})
        docs = response.get("docs", [])
        last_cursor = current_cursor
        current_cursor = payload.get("nextCursorMark")
        if current_cursor is None:
            raise RuntimeError("Solr response missing nextCursorMark")

        params["cursorMark"] = current_cursor

        for document in docs:
            if isinstance(document, dict):
                document_id = first_value(document.get("id"))
                if document_id:
                    yield document

def kbart_rows(
    inst_id: str, batch_size: int
) -> Generator[tuple[dict[str, str] | None, dict[str, str] | None]]:

    for record in matching_solr_records(inst_id, batch_size):
        row = build_kbart_row(record)
        # TODO not sure if this is worth the hassle of reporting this way --
        # things with missing titles aren't our problem. Log elsewhere,
        # skip/ignore, and
        # move on?
        if not row["publication_title"] or not row["title_id"]:
            yield (
                None,
                {"catalog_id": str(record.get("id")), "reason": "required source fields missing"},
            )
        else:
            yield row, None


def generate_kbart_export(
    inst_id: str,
    output_file: Path,
    metadata_file: Path,
    error_file: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[int, int]:

    # TODO extract class w/ parameters?

    row_count = 0
    error_count = 0
    processed_records = 0

    error_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8", newline="") as output_fh:
        with error_file.open("w", encoding="utf-8", newline="") as error_fh:
            report_writer = csv.DictWriter(output_fh, fieldnames=KBART_COLUMN_ORDER, delimiter="\t")
            report_writer.writeheader()

            error_writer = csv.DictWriter(
                error_fh, fieldnames=["catalog_id", "reason"], delimiter="\t"
            )
            error_writer.writeheader()

            for row, error in kbart_rows(inst_id, batch_size):
                processed_records += 1
                if row is not None:
                    row_count += 1
                    report_writer.writerow(
                        {field: row.get(field, "") for field in KBART_COLUMN_ORDER}
                    )
                if error is not None:
                    error_count += 1
                    error_writer.writerow(
                        {
                            "catalog_id": error.get("catalog_id", ""),
                            "reason": error.get("reason", ""),
                        }
                    )

    metadata_summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "inst_id": inst_id,
        "output_file": str(output_file),
        "error_file": str(error_file),
        "processed_records": processed_records,
        "written_rows": row_count,
        "skipped_rows": error_count,
        "column_order": KBART_COLUMN_ORDER,
    }

    write_metadata_summary(metadata_file, metadata_summary)
    return row_count, error_count


if __name__ == "__main__":
    main()
