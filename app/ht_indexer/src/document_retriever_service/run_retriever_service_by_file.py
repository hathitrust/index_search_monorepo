"""This use case is for testing and processing a huge list of documents extracted from the production environment."""

import argparse
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ht_queue_service.queue_config import QueueParams
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_mysql import HtMysql

from document_retriever_service.full_text_search_retriever_service import (
    FullTextSearchRetrieverQueueService,
    PublishCounts,
    run_retriever_service_threads,
)
from document_retriever_service.ht_status_retriever_service import get_non_processed_ids
from document_retriever_service.retriever_arguments import RetrieverServiceByFileArguments

logger = get_ht_logger(name=__name__)

# ht_id = lowercase namespace + "." + id, e.g. mdp.39015078560292 or uc2.ark:/13960/t0dv1g69b.
# Whitespace and commas are rejected: Solr's {!terms} parser splits on commas.
HT_ID_PATTERN = re.compile(r"^[a-z0-9]+\.[^\s,]+$")
# Catalog record id: 9 digits, e.g. 008394936
RECORD_ID_PATTERN = re.compile(r"^\d{9}$")
ID_PATTERNS = {"item": HT_ID_PATTERN, "record": RECORD_ID_PATTERN}


@dataclass
class IdsFile:
    """IDs read from the input file, after stripping, de-duplication and validation."""

    ids: list[str] = field(default_factory=list)  # unique, valid ids, in file order
    requested: int = 0  # non-blank lines in the file
    duplicates: int = 0
    invalid: list[str] = field(default_factory=list)


@dataclass
class ByFileSummary:
    """Counts logged at the end of a run. seeded = published to the queue, errors = catalog
    metadata or publish failures, not_found = ht_ids Catalog did not return (item mode only)."""

    requested: int
    duplicates: int
    invalid: list[str]
    already_processed: int
    seeded: int
    errors: int
    not_found: int


def read_ids_from_file(input_documents_file: str | Path, query_field: str) -> IdsFile:
    """Read one id per line: strip whitespace, skip blank lines, de-duplicate and validate.

    :param input_documents_file: file with one ht_id (item) or record id (record) per line
    :param query_field: item or record; selects the id format to validate against
    """
    pattern = ID_PATTERNS[query_field]
    ids_file = IdsFile()
    seen: set[str] = set()

    with open(input_documents_file) as f:
        for line in f:
            doc_id = line.strip()
            if not doc_id:
                continue
            ids_file.requested += 1
            if doc_id in seen:
                ids_file.duplicates += 1
                continue
            seen.add(doc_id)
            if pattern.match(doc_id):
                ids_file.ids.append(doc_id)
            else:
                ids_file.invalid.append(doc_id)

    return ids_file


def log_summary(summary: ByFileSummary) -> None:
    logger.info(
        f"Retriever by file summary: requested={summary.requested} "
        f"duplicates={summary.duplicates} invalid={len(summary.invalid)} "
        f"already_processed={summary.already_processed} "
        f"seeded={summary.seeded} errors={summary.errors} not_found={summary.not_found}"
    )


def retrieve_documents_by_file(
    queue_params: QueueParams,
    query_field: str,
    solr_host: str | None,
    solr_user: str | None,
    solr_password: str | None,
    solr_retriever_query_params: dict[str, Any],
    input_documents_file: str | Path,
    status_file: str | Path,
    parallelize: bool,
    db_conn: HtMysql,
    max_workers: int,
) -> ByFileSummary:
    """This method is used to retrieve the documents from the Catalog and generate the full-text search entry.
    The list of documents to index is extracted from a file.

    :param queue_params: The object with the queue parameters
    :param query_field: The field to use in the query
    :param solr_host: The host of the Solr server
    :param solr_user: The user of the Solr server
    :param solr_password: The password of the Solr server
    :param solr_retriever_query_params: The query parameters to use in the Solr query
    :param input_documents_file: The file containing the list of documents to process
    :param status_file: The file to store the status of the documents
    :param parallelize: If True, the processing will be done in parallel
    :param db_conn: The database connection
    :param max_workers: The maximum number of workers to use in parallel processing
    :return: the run summary, also logged as one line
    """

    if not os.path.isfile(input_documents_file):
        logger.info("Provide the file with the list of ids to process is a required parameter")
        exit()

    document_retriever_service = FullTextSearchRetrieverQueueService(
        queue_params, solr_host, solr_user, solr_password, solr_retriever_query_params
    )

    ids_file = read_ids_from_file(input_documents_file, query_field)
    # Logs invalidIDs
    for doc_id in ids_file.invalid:
        logger.error(f"Invalid {query_field} id {doc_id!r} in {input_documents_file}: skipped")

    ids2process, processed_ids = get_non_processed_ids(status_file, ids_file.ids)
    already_processed = len(ids_file.ids) - len(ids2process)

    logger.info(f"Total of items to process {len(ids2process)}")

    with open(status_file, "w") as tmp_file_status:
        for doc in processed_ids:
            tmp_file_status.write(doc + "\n")

    counts = PublishCounts()
    try:
        while ids2process:
            list_documents, ids2process = ids2process[:200], ids2process[200:]

            start_time = time.time()

            logger.info(f"Total of documents to process {len(list_documents)}")

            if parallelize:
                # Run retriever service in threads
                counts += run_retriever_service_threads(
                    db_conn,
                    list_documents,
                    query_field,
                    document_retriever_service,
                    max_workers,
                )

            else:
                # Run retriever service sequentially
                counts += document_retriever_service.full_text_search_retriever_service(
                    db_conn, list_documents, query_field
                )

            logger.info(
                f"Total time to retrieve and generate documents {time.time() - start_time:.10f}"
            )
    finally:
        # Log the summary even if a Solr error stops the run, so the counts so far are visible
        summary = ByFileSummary(
            requested=ids_file.requested,
            duplicates=ids_file.duplicates,
            invalid=ids_file.invalid,
            already_processed=already_processed,
            seeded=counts.published,
            errors=counts.failed,
            not_found=counts.not_found,
        )
        log_summary(summary)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser()

    init_args_obj = RetrieverServiceByFileArguments(parser)

    retrieve_documents_by_file(
        init_args_obj.queue_config.queue_params,
        init_args_obj.query_field,
        init_args_obj.solr_host,
        init_args_obj.solr_user,
        init_args_obj.solr_password,
        init_args_obj.solr_retriever_query_params,
        init_args_obj.input_documents_file,
        init_args_obj.status_file,
        init_args_obj.parallelize,
        init_args_obj.db_conn,
        init_args_obj.max_workers,
    )


if __name__ == "__main__":
    main()
