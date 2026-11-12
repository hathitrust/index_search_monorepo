"""Generate a KBART 3.0 TSV given an organization ID"""

from __future__ import annotations

import csv
import re
from collections.abc import Generator, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import click
import structlog
from ht_search.export_all_results import SolrExporter, SolrResult
from ht_utils.ht_env_config import HtEnvConfig
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import (
    normalize_catalog_id_stripped_zeros,
    write_metadata_summary,
)
from ht_utils.text_processor import first_value

logger = get_ht_logger(name=__name__)


DEFAULT_OUTPUT_PATH = Path(__file__).parent / "output"
DEFAULT_BATCH_SIZE = 1000

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


class KBARTFileGenerator:
    def __init__(self, inst_id: str, batch_size: int, output_path: Path) -> None:

        if not re.match(r"^[A-Za-z0-9-]+$", inst_id):
            raise ValueError(
                "inst_id not valid (must contain only alphanumeric characters and '-')"
            )

        self.inst_id = inst_id
        self.output_path = output_path
        self.batch_size = batch_size
        self.processed_records = 0
        self.error_count = 0
        self.row_count = 0

    @staticmethod
    def extract_dates(ht_id_display: Sequence[str]) -> tuple[str, str]:
        """
        returns the earliest & latest dates from the items in a record. ignore
        empty dates, dates equal to 9999 (unknown), and dates without 4 digits. If
        there are no valid dates, returns empty string for both dates.
        """

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
        filtered_dates = [
            d for d in dates if d and d is not None and d != str(9999) and len(d) == 4
        ] or [""]

        return min(filtered_dates), max(filtered_dates)

    @staticmethod
    def build_kbart_row(
        metadata: SolrResult,
    ) -> dict[str, str]:
        raw_id = metadata.first_value("id")
        title_id = normalize_catalog_id_stripped_zeros(raw_id)
        identifiers = metadata.list_values("isbn") or metadata.list_values("issn")
        # remove trailing commas
        publisher_name = " ".join(metadata.list_values("publisher")).rstrip(",")
        oclc_number = metadata.first_value("oclc")
        title_display = metadata.first_value("title_display")
        title = metadata.first_value("title")
        vtitle = metadata.first_value("vtitle")
        mainauthor = metadata.first_value("mainauthor")
        (min_date, max_date) = KBARTFileGenerator.extract_dates(
            metadata.list_values("ht_id_display")
        )
        display_date = metadata.first_value("display_date")
        is_serial = "Serial" in metadata.list_values("format")
        is_monograph = "Book" in metadata.list_values("format")

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
            "date_first_issue_online": min_date if is_serial else "",
            # null
            "num_first_vol_online": "",
            # null
            "num_first_issue_online": "",
            # Similar to date_first, if we are able to identify the most recent year value, use that. If not, leave blank
            "date_last_issue_online": max_date if is_serial else "",
            # null
            "num_last_vol_online": "",
            # null
            "num_last_issue_online": "",
            # Use the solr value of id, stripped of leading 0s, to create a link to the title level record.
            "title_url": f"https://catalog.hathitrust.org/Record/{title_id}",
            # for monograph, use first value in solr field 'mainauthor'; for serials leave null
            "contributor": "" if is_serial else mainauthor,
            # if 'mainauthor' is present in sorl record, value is 'Author', otherwise null
            "contributor_type": "author" if mainauthor and not is_serial else "",
            # use solr field id_int
            "title_id": title_id,
            # null
            "embargo_info": "",
            # always value 'full',
            "coverage_depth": "full",
            # value: "Access is variable and dependent on resource sharing participation"
            "notes": "Access is variable and dependent on resource sharing participation",
            # solr field value: publisher, remove trailing punctuation
            "publisher_name": publisher_name,
            # from "format" in solr. Where value contains "serial" should be 'Serial'. Where contains "book" should be "monograph"
            "publication_type": "serial" if is_serial else "monograph" if is_monograph else "",
            # value is 'text'
            "content_type": "text",
            # When we have year values, in the 974$y, especially for serials and MPMs, are we able to identify the earliest of those values? If so, use that value; if not, use solr display_date
            "date_monograph_published_print": display_date if not is_serial else "",
            # null,
            "date_monograph_published_online": "",
            # null
            "monograph_volume": "",
            # from Edition field in solr
            "monograph_edition": metadata.first_value("edition"),
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

    def matching_solr_records(self) -> Generator[SolrResult]:
        env_config = HtEnvConfig()

        solr_exporter = SolrExporter(
            env_config.catalog_solr_ro_url,
            "env-not-used",
            user=env_config.solr_user,
            password=env_config.solr_password,
        )

        params = {
            "q": "*:*",
            "fq": f'print_holdings:{self.inst_id} OR ht_availability:"Full text"',
            "fl": ",".join(SOLR_FIELDS),
        }
        records_processed = 0

        for document in solr_exporter.run_cursor_raw(
            solr_params=params, batch_size=self.batch_size
        ):
            records_processed += 1
            if (records_processed / self.batch_size) % 100 == 0:
                logger.info(
                    f"{records_processed} processed ({records_processed / self.batch_size} pages of results)"
                )

            document_id = document.first_value("id")
            if document_id:
                yield document
            else:
                self.error_count += 1
                logger.warning("Can't process record (id missing)")

    def kbart_rows(self) -> Generator[dict[str, str]]:
        for record in self.matching_solr_records():
            self.processed_records += 1
            row = self.build_kbart_row(record)
            # TODO not sure if this is worth the hassle of reporting this way --
            # things with missing titles aren't our problem. Log elsewhere,
            # skip/ignore, and
            # move on?
            if not row["publication_title"] or not row["title_id"]:
                self.error_count += 1
                logger.warning(
                    f"Can't process record {record.first_value('id')}: output publication_title or title_id fields missing"
                )
            else:
                self.row_count += 1
                yield row

    def generate_kbart_export(
        self,
    ) -> tuple[int, int]:

        # TODO extract class w/ parameters?

        file_prefix = f"kbart_{self.inst_id}_{date.today()}"

        self.output_path.mkdir(parents=True, exist_ok=True)
        output_file = self.output_path / f"{file_prefix}.tsv"
        metadata_file = self.output_path / f"{file_prefix}.metadata.json"

        logger.info(f"Generating KBART report for {self.inst_id}")

        logger.info(f"Output to {output_file}")
        logger.info(f"Summary in {metadata_file}")
        logger.info(f"Querying solr in batches of {self.batch_size}")

        with output_file.open("w", encoding="utf-8", newline="") as output_fh:
            report_writer = csv.DictWriter(output_fh, fieldnames=KBART_COLUMN_ORDER, delimiter="\t")
            report_writer.writeheader()

            for row in self.kbart_rows():
                report_writer.writerow({field: row.get(field, "") for field in KBART_COLUMN_ORDER})

        metadata_summary = {
            "generated_at": datetime.now(UTC).isoformat(),
            "inst_id": self.inst_id,
            "output_file": str(output_file),
            "processed_records": self.processed_records,
            "written_rows": self.row_count,
            "skipped_rows": self.error_count,
            "column_order": KBART_COLUMN_ORDER,
        }

        write_metadata_summary(metadata_file, metadata_summary)
        logger.info("Generated %d KBART rows", self.row_count)
        if self.error_count > 0:
            logger.warning("Skipped %d catalog_ids during KBART generation", self.error_count)

        return self.row_count, self.error_count


@click.command()
@click.argument("inst-id", type=str, help="Institution ID to generate a report for.")
@click.option(
    "--output-path", "-o", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output KBART TSV path."
)
@click.option(
    "--batch-size",
    type=int,
    default=DEFAULT_BATCH_SIZE,
    help="Maximum number of rows to fetch per Solr request.",
)
def main(inst_id: str, output_path: Path, batch_size: int) -> None:
    """Generate a KBART TSV from solr records for a given institution."""
    KBARTFileGenerator(inst_id, batch_size, output_path).generate_kbart_export()


if __name__ == "__main__":
    structlog.reset_defaults()
    main()
