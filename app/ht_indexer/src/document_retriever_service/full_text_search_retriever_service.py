import argparse
import copy
import json
import sys
import time
from collections.abc import Collection
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import requests
from catalog_metadata.catalog_metadata import CatalogItemMetadata, CatalogRecordMetadata
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_queue_service.queue_config import QueueParams
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import (
    get_error_message_by_document,
    get_general_error_message,
    split_into_batches,
)
from ht_utils.query_maker import make_solr_term_query

from document_retriever_service.retriever_arguments import RetrieverServiceArguments
from document_retriever_service.retriever_services_utils import RetrieverServicesUtils

logger = get_ht_logger(name=__name__)

SOLR_BATCH_SIZE = 200  # The chunk size is 200, because Solr will fail with the status code 414. The chunk size was determined
# by testing the Solr query with different values (e.g., 100-500 and with 200 ht_ids it worked.


@dataclass(frozen=True)
class PublishCounts:
    """How many items were published to the queue, how many failed (catalog metadata error or
    publish error) and how many requested ht_ids Catalog did not return (item mode only)."""

    published: int = 0
    failed: int = 0
    not_found: int = 0

    def __add__(self, other: PublishCounts) -> PublishCounts:
        return PublishCounts(
            self.published + other.published,
            self.failed + other.failed,
            self.not_found + other.not_found,
        )


@dataclass
class ChunkMetadata:
    """Items built from one Solr response, and the ht_ids whose catalog metadata failed."""

    items: list[CatalogItemMetadata] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)  # ht_id -> error message


class FullTextSearchRetrieverQueueService:
    """
    This class is responsible to retrieve the documents from the Catalog and generate the full text search entry
    There are three main use cases:
        1- Retrieve all the items of a record in the Catalog - the query will contain the id of the record
        2- Retrieve a specific item of a record in the Catalog - the query will contain the ht_id of the item
        3- Retrieve all the items of all the records in the Catalog - the query will be *:*
    By default, the query is None, then an error will be raised if the query is not provided
    All the entries are published in a queue
    """

    def __init__(
        self,
        queue_params: QueueParams | None = None,
        solr_host: str | None = None,
        solr_user: str | None = None,
        solr_password: str | None = None,
        solr_retriever_query_params: dict[str, Any] | None = None,
    ):

        self.solr_host = solr_host
        self.solr_user = solr_user
        self.solr_password = solr_password
        self.solr_retriever_query_params = solr_retriever_query_params

        # Queue configuration
        self.queue_params = queue_params

    @staticmethod
    def get_queue_producer(queue_params: QueueParams) -> QueueProducer | None:
        """Establish a connection to the queue to publish the documents"""

        try:
            queue_producer = QueueProducer(queue_params)
            return queue_producer

        except Exception as e:
            logger.error(
                f"Environment variables required: "
                f"{get_general_error_message('DocumentGeneratorService', e)}"
            )
            return None

    @staticmethod
    def generate_metadata(record: CatalogItemMetadata) -> tuple[dict[str, Any], str]:
        """Generate the metadata and the ht_id of the document to be published in the queue"""

        item_id = record.ht_id
        logger.info(f"Processing document htid={item_id}")

        item_metadata = record.metadata
        item_metadata["ht_id"] = item_id

        return item_metadata, item_id

    @staticmethod
    def publishing_documents(
        queue_producer_conn: QueueProducer | None,
        result: list[CatalogItemMetadata],
        metadata_failures: dict[str, str] | None = None,
    ) -> PublishCounts:
        published = 0
        failed = 0

        for record in result:
            item_metadata, item_id = FullTextSearchRetrieverQueueService.generate_metadata(record)
            logger.info(f"Publishing document htid={item_id}")

            try:
                if queue_producer_conn is None:
                    raise RuntimeError("Unable to establish a queue connection")
                RetrieverServicesUtils.publish_document(queue_producer_conn, item_metadata)
                published += 1

            except Exception as e:
                error_info = get_error_message_by_document(
                    "FullTextSearchRetrieverQueueService", e, item_metadata
                )
                logger.error(f"Error in publishing document htid={item_id} {error_info}")
                failed += 1

        # Metadata failures are never published; count them as failed. They are already
        # logged by _fail_metadata (called from generate_chunk_metadata), so don't log again.
        failed += len(metadata_failures or {})

        return PublishCounts(published=published, failed=failed)

    def retrieve_documents_from_solr(
        self, solr_query: str, solr_retriever: HTSolrAPI
    ) -> requests.Response:
        """Function to retrieve documents from Solr
        :param solr_query:
        :param solr_retriever: HTSolrAPI object
        :return: response from Solr
        """

        if self.solr_retriever_query_params is None:
            raise RuntimeError("solr_retriever_query_params is required")

        if self.solr_host is None:
            raise RuntimeError("solr_host is required")
        chunk_solr_params = copy.deepcopy(self.solr_retriever_query_params)

        chunk_solr_params["fq"] = solr_query

        response = solr_retriever.send_solr_request(
            solr_host=f"{self.solr_host.rstrip('/')}/query", solr_params=chunk_solr_params
        )
        if response.status_code != 200:
            logger.error(f"Error {response.status_code} in query: {solr_query}")
            raise requests.exceptions.RequestException(
                f"Error {response.status_code} in query: {solr_query}"
            )
        return response

    @staticmethod
    def generate_chunk_metadata(
        chunk: list[str], solr_output: dict[str, Any], by_field: str = "item"
    ) -> ChunkMetadata:
        """Generate the metadata for the documents

        A metadata error fails only the affected ht_ids: one item if building that item fails,
        or every item of the record (only the requested ones in item mode) if the record fails.

        :param chunk: list of documents to process
        :param solr_output: response from Solr
        :param by_field: field to search by (item=ht_id or record=id)
        :return: the items built, and the ht_ids whose metadata failed
        """

        chunk_metadata = ChunkMetadata()
        requested = set(chunk)
        for record in (solr_output.get("response") or {}).get("docs", []):
            item_ids: list[str] = record.get("ht_id") or []
            if by_field != "record":
                # Query was by ht_id: keep only the requested items, not every item of the record
                item_ids = [item_id for item_id in item_ids if item_id in requested]

            try:
                # Object that maps the record with their Catalog metadata
                catalog_record_metadata = CatalogRecordMetadata(record)
            except Exception as e:
                FullTextSearchRetrieverQueueService._fail_metadata(chunk_metadata, item_ids, e)
                continue

            for item_id in item_ids:
                try:
                    chunk_metadata.items.append(
                        RetrieverServicesUtils.get_catalog_object(item_id, catalog_record_metadata)
                    )
                except Exception as e:
                    FullTextSearchRetrieverQueueService._fail_metadata(chunk_metadata, [item_id], e)
        return chunk_metadata

    @staticmethod
    def _fail_metadata(chunk_metadata: ChunkMetadata, item_ids: list[str], e: Exception) -> None:
        """Record and log the ht_ids whose catalog metadata could not be built."""
        for item_id in item_ids:
            chunk_metadata.failed[item_id] = str(e)
            logger.error(
                f"Error in building catalog metadata for document htid={item_id} "
                f"{get_general_error_message('FullTextSearchRetrieverQueueService', e)}"
            )

    @staticmethod
    def log_ht_ids_not_in_catalog(
        chunk: list[str],
        record_metadata_list: list[CatalogItemMetadata],
        failed_ht_ids: Collection[str] = (),
    ) -> set[str]:
        """Log the ht_ids requested in the chunk that Catalog did not return.
        Only valid when the chunk holds ht_ids (by_field != "record").

        :param chunk: list of ht_ids sent to Solr
        :param record_metadata_list: items returned by Catalog
        :param failed_ht_ids: ht_ids Catalog returned but whose metadata failed; not missing
        :return: set of ht_ids not found in Catalog
        """
        missing = (
            set(chunk) - {record.ht_id for record in record_metadata_list} - set(failed_ht_ids)
        )
        for item_id in sorted(missing):
            logger.error(
                f"Error in retrieving document htid={item_id} "
                f"FullTextSearchRetrieverQueueService_not found in Catalog"
            )
        return missing

    def full_text_search_retriever_service(
        self, initial_documents: list[str], by_field: str = "item"
    ) -> PublishCounts:
        """
        This method is used to retrieve the documents from the Catalog and generate the full text search entry
        If the Solr is not available, an error will be raised, and the process will be stopped

        We run Solr queries in batch
        Each batch will retrieve 200 documents because Solr will fail with the status code 414
        if the URI is too Long.

        :return: total of items published, failed and not found in Catalog, across all chunks
        """

        if self.queue_params is None:
            raise RuntimeError("queue_params is required")
        if self.solr_host is None:
            raise RuntimeError("solr_host is required")

        # Create a connection to the queue to produce messages
        queue_producer = FullTextSearchRetrieverQueueService.get_queue_producer(self.queue_params)

        solr_retriever = HTSolrAPI(self.solr_host, self.solr_user, self.solr_password)

        counts = PublishCounts()

        # As we have a long list of ht_ids/ids, the recommendation is to split the list of documents into chunks
        # and create query batch to avoid the Solr URI too long error.
        # The chunk size is 200, because Solr will fail with the status code 414. The chunk size was determined
        # by testing the Solr query with different values (e.g., 100-500 and with 200 ht_ids it worked.

        # Create chunk of documents to process according to the Solr query batch size
        for chunk in split_into_batches(initial_documents, SOLR_BATCH_SIZE):
            # Build the query to retrieve the total of documents to process
            query = make_solr_term_query(chunk, by_field)

            # Retrieve the documents from Solr
            response = self.retrieve_documents_from_solr(query, solr_retriever)
            output = json.loads(response.content.decode("utf-8"))

            # Generate the metadata for the documents
            start_time = time.time()
            chunk_metadata = FullTextSearchRetrieverQueueService.generate_chunk_metadata(
                chunk, output, by_field
            )

            # In record mode the chunk holds record ids, so it can't be compared with ht_ids
            if by_field != "record":
                not_found = FullTextSearchRetrieverQueueService.log_ht_ids_not_in_catalog(
                    chunk, chunk_metadata.items, chunk_metadata.failed
                )
                counts += PublishCounts(not_found=len(not_found))

            logger.info(f"Metadata generator: Total items = {len(chunk_metadata.items)}.")
            logger.info(f"Metadata generator: Total time = {time.time() - start_time}")

            # Publish the documents in the queue; metadata failures are recorded as failed
            counts += FullTextSearchRetrieverQueueService.publishing_documents(
                queue_producer, chunk_metadata.items, chunk_metadata.failed
            )

        return counts


def run_retriever_service_threads(
    list_documents: list[str],
    by_field: str,
    document_retriever_service: FullTextSearchRetrieverQueueService,
    max_workers: int,
) -> PublishCounts:
    """
    Run the retriever service across multiple threads.

    The number of threads is capped at MAX_WORKERS (currently 20) and defaults to
    `multiprocessing.cpu_count() * 2`.

    :param list_documents:
    :param by_field:
    :param document_retriever_service:
    :param max_workers: Number of threads to use
    :return: total of items published, failed and not found in Catalog. A batch whose thread
        failed counts all its ids as failed.
    """

    total_documents = len(list_documents)

    if total_documents <= 0:
        logger.info("Nothing to process")
        return PublishCounts()

    batch_size = round(total_documents / max_workers + 0.5)
    # Create batches for thread processing
    document_batches = [
        list_documents[i : i + batch_size] for i in range(0, total_documents, batch_size)
    ]

    start_time = time.time()
    counts = PublishCounts()

    # Use ThreadPoolExecutor instead of multiprocessing.Process
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks to the thread pool
        future_to_batch = {
            executor.submit(
                document_retriever_service.full_text_search_retriever_service,
                batch,
                by_field,
            ): batch
            for batch in document_batches
        }

        # Wait for all threads to complete and handle any exceptions
        for future in as_completed(future_to_batch):
            batch = future_to_batch[future]
            try:
                counts += future.result()  # This will raise an exception if the thread failed
                logger.debug(f"Successfully processed batch of {len(batch)} documents")
            except Exception as e:
                logger.error(f"Thread failed processing batch of {len(batch)} documents: {e}")
                counts += PublishCounts(failed=len(batch))

    logger.info(
        f"Threading=retrieving: Total time to retrieve documents {time.time() - start_time:.10f}"
    )
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()

    init_args_obj = RetrieverServiceArguments(parser)

    # comma_separated_list("") returns [""], so drop blank ids before checking
    list_documents = [doc_id.strip() for doc_id in init_args_obj.list_documents if doc_id.strip()]
    if not list_documents:
        logger.error("--list_documents is required")
        sys.exit(1)

    document_retriever_service = FullTextSearchRetrieverQueueService(
        init_args_obj.queue_config.queue_params,
        init_args_obj.solr_host,
        init_args_obj.solr_user,
        init_args_obj.solr_password,
        init_args_obj.solr_retriever_query_params,
    )

    by_field = init_args_obj.query_field

    logger.info(f"Process=retrieving: Total of documents to process {len(list_documents)}")

    if init_args_obj.parallelize:
        counts = run_retriever_service_threads(
            list_documents,
            by_field,
            document_retriever_service,
            init_args_obj.max_workers,
        )
    else:
        counts = document_retriever_service.full_text_search_retriever_service(
            list_documents, by_field
        )

    logger.info(
        "Process=retrieving: run summary",
        published=counts.published,
        failed=counts.failed,
        not_found=counts.not_found,
    )
    # Logs are the only record of failed items, so exit non-zero to let the caller know
    if counts.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
