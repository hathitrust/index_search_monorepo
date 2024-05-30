"""This an use case for testing and process a huge lis of documents extracted from production environment."""
import argparse
import os
import sys
import inspect
import time

from document_retriever_service.full_text_search_retriever_service import FullTextSearchRetrieverQueueService, \
    run_retriever_service
from document_retriever_service.retriever_arguments import RetrieverServiceByFileArguments
from ht_document.ht_document import logger
from document_retriever_service.ht_status_retriever_service import get_non_processed_ids

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)


def retrieve_documents_by_file(solr_api_url, queue_name, queue_host, queue_user, queue_password, dead_letter_queue,
                               input_documents_file, query_field, start, rows, status_file, parallelize, nthreads):
    """ This method is used to retrieve the documents from the Catalog and generate the full text search entry.
    The list of documents to index is extracted from a file.

    :param solr_api_url: Solr API URL
    :param queue_name: Queue name
    :param queue_host: Queue host
    :param queue_user: Queue user
    :param queue_password: Queue password
    :param dead_letter_queue: Boolean parameter indicating the error messages will send to a dead letter queue
    :param input_documents_file: File with the list of documents to process
    :param query_field: Query field
    :param start: Start Solr query
    :param rows: rows
    :param status_file: Status file
    """

    document_indexer_service = FullTextSearchRetrieverQueueService(
        solr_api_url,
        queue_name,
        queue_host,
        queue_user,
        queue_password,
        dead_letter_queue)

    if os.path.isfile(input_documents_file):
        with open(input_documents_file) as f:
            list_ids = f.read().splitlines()

            ids2process, processed_ids = get_non_processed_ids(status_file, list_ids)

            logger.info(f"Total of items to process {len(ids2process)}")

            tmp_file_status = open(os.path.join(current, "document_retriever_status.txt"), "w+")
            for doc in processed_ids:
                tmp_file_status.write(doc + "\n")
            tmp_file_status.close()

            while ids2process:
                list_documents, ids2process = ids2process[:200], ids2process[200:]

                start_time = time.time()

                logger.info(f"Total of documents to process {len(list_documents)}")

                total_documents = len(list_documents)
                run_retriever_service(parallelize, nthreads, total_documents, list_documents, query_field,
                                      document_indexer_service,
                                      start,
                                      rows)

                logger.info(f"Total time to retrieve and generate documents {time.time() - start_time:.10f}")

    else:
        logger.info("Provide the file with the list of ids to process is a required parameter")
        exit()


def main():
    parser = argparse.ArgumentParser()

    init_args_obj = RetrieverServiceByFileArguments(parser)

    # TODO: Review the logic of the status file
    status_file = os.path.join(current, "document_retriever_status.txt")

    parallelize = True
    nthreads = None

    retrieve_documents_by_file(init_args_obj.solr_api_url, init_args_obj.queue_name, init_args_obj.queue_host,
                               init_args_obj.queue_user, init_args_obj.queue_password, init_args_obj.dead_letter_queue,
                               init_args_obj.input_documents_file, init_args_obj.query_field,
                               init_args_obj.start, init_args_obj.rows,
                               status_file, parallelize, nthreads)


if __name__ == "__main__":
    main()
