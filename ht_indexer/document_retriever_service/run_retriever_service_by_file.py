"""This use case is for testing and processing a huge list of documents extracted from the production environment."""
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

PARALLELIZE = True

def retrieve_documents_by_file(queue_name, queue_host, queue_user, queue_password,
                               query_field, solr_host, solr_user, solr_password, solr_retriever_query_params,
                               input_documents_file, status_file, parallelize=PARALLELIZE):
    """ This method is used to retrieve the documents from the Catalog and generate the full text search entry.
    The list of documents to index is extracted from a file.

    :param queue_name: The name of the queue to use
    :param queue_host: The host of the queue
    :param queue_user: The user of the queue
    :param queue_password: The password of the queue
    :param query_field: The field to use in the query
    :param solr_host: The host of the Solr server
    :param solr_user: The user of the Solr server
    :param solr_password: The password of the Solr server
    :param solr_retriever_query_params: The query parameters to use in the Solr query
    :param input_documents_file: The file containing the list of documents to process
    :param status_file: The file to store the status of the documents
    :param parallelize: If True, the processing will be done in parallel
    """

    document_retriever_service = FullTextSearchRetrieverQueueService(queue_name, queue_host, queue_user, queue_password,
                        solr_host, solr_user, solr_password, solr_retriever_query_params)

    if os.path.isfile(input_documents_file):
        with open(input_documents_file) as f:
            list_ids = f.read().splitlines()

            ids2process, processed_ids = get_non_processed_ids(status_file, list_ids)

            logger.info(f"Total of items to process {len(ids2process)}")

            with open(status_file, "w") as tmp_file_status:
                for doc in processed_ids:
                    tmp_file_status.write(doc + "\n")
                tmp_file_status.close()

            while ids2process:
                list_documents, ids2process = ids2process[:200], ids2process[200:]

                start_time = time.time()

                logger.info(f"Total of documents to process {len(list_documents)}")

                run_retriever_service(list_documents, query_field,
                                      document_retriever_service,
                                    parallelize=parallelize
                                      )

                logger.info(f"Total time to retrieve and generate documents {time.time() - start_time:.10f}")

    else:
        logger.info("Provide the file with the list of ids to process is a required parameter")
        exit()


def main():
    parser = argparse.ArgumentParser()

    init_args_obj = RetrieverServiceByFileArguments(parser)

    # TODO: Review the logic of the status file
    status_file = os.path.join(current, "document_retriever_status.txt")

    retrieve_documents_by_file(init_args_obj.queue_name, init_args_obj.queue_host,
                               init_args_obj.queue_user, init_args_obj.queue_password,
                               init_args_obj.query_field,
                               init_args_obj.solr_host,
                               init_args_obj.solr_user,
                               init_args_obj.solr_password,
                               init_args_obj.solr_retriever_query_params,
                               init_args_obj.input_documents_file,
                               status_file,
                               parallelize=PARALLELIZE)

if __name__ == "__main__":
    main()
