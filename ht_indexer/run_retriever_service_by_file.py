"""This an use case for testing and process a huge lis of documents extracted from production environment."""
import argparse
import os
import sys
import inspect
import time

from document_retriever_service.full_text_search_retriever_service import FullTextSearchRetrieverQueueService, \
    run_retriever_service
from document_retriever_service.retriever_arguments import RetrieverServiceArguments
from ht_document.ht_document import logger
from document_retriever_service.ht_status_retriever_service import get_non_processed_ids

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)


def main():
    parser = argparse.ArgumentParser()

    init_args_obj = RetrieverServiceArguments(parser)

    document_indexer_service = FullTextSearchRetrieverQueueService(
        init_args_obj.solr_api_url,
        init_args_obj.queue_name,
        init_args_obj.queue_host,
        init_args_obj.queue_user,
        init_args_obj.queue_password)

    # TODO: Review the logic of the status file
    status_file = os.path.join(current, "document_retriever_status.txt")

    list_documents_file = os.path.join(current, "filter_ids.txt")
    if os.path.isfile(list_documents_file):
        # If a document with the list of id to process is received as a parameter, then create batch of queries
        with open(list_documents_file) as f:
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
                parallelize = True

                nthreads = None

                total_documents = len(list_documents)
                run_retriever_service(parallelize, nthreads, total_documents, list_documents, init_args_obj.query_field,
                                      document_indexer_service,
                                      init_args_obj)

                logger.info(f"Total time to retrieve and generate documents {time.time() - start_time:.10f}")

    else:
        logger.info("Provide the file with the list of ids to process is a required parameter")
        exit()


if __name__ == "__main__":
    main()
