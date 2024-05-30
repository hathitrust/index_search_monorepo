import argparse
import inspect
import os
import sys
import time
import multiprocessing

import ht_utils.ht_utils
from document_retriever_service.catalog_retriever_service import CatalogRetrieverService
from document_retriever_service.retriever_arguments import RetrieverServiceArguments
from ht_utils.ht_logger import get_ht_logger
from ht_queue_service.queue_producer import QueueProducer

logger = get_ht_logger(name=__name__)

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

PROCESSES = multiprocessing.cpu_count() - 1


def publish_document(queue_producer, content: dict = None):
    """
    Publish the document in a queue
    """
    message = content
    logger.info(f"Sending message with id {content.get('ht_id')} to queue {queue_producer.queue_name}")
    queue_producer.publish_messages(message)


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

    def __init__(self,
                 solr_api_url,
                 queue_name: str = 'retriever_queue', queue_host: str = None,
                 queue_user: str = None,
                 queue_password: str = None,
                 dead_letter_queue: bool = False):

        self.solr_api_url = solr_api_url
        self.queue_name = queue_name
        self.queue_host = queue_host
        self.queue_user = queue_user
        self.queue_password = queue_password
        self.dead_letter_queue = dead_letter_queue

    def full_text_search_retriever_service(self, initial_documents, start, rows, by_field: str = 'item'):
        """
        This method is used to retrieve the documents from the Catalog and generate the full text search entry
        If the Solr is not available, an error will be raised, and the process will be stopped
        """
        # Create a connection to Solr Api
        catalog_retriever = CatalogRetrieverService(self.solr_api_url)

        try:
            # Create a connection to the queue
            queue_producer = QueueProducer(self.queue_user, self.queue_password, self.queue_host, self.queue_name,
                                           self.dead_letter_queue)
        except Exception as e:
            logger.error(f"Environment variables required: "
                         f"{ht_utils.ht_utils.get_general_error_message('DocumentGeneratorService', e)}")
        try:
            total_documents = catalog_retriever.count_documents(initial_documents, start, rows, by_field)
        except Exception as e:
            error_info = ht_utils.ht_utils.get_general_error_message("FullTextSearchRetrieverQueueService",
                                                                     e)

            logger.error(f"Error in getting documents from Solr {error_info}")
            exit(1)

        count_records = 0
        processed_items = []
        while count_records < total_documents:
            chunk = initial_documents[count_records:count_records + rows]

            try:
                result = catalog_retriever.retrieve_documents(chunk, start, rows, by_field=by_field)
            except Exception as e:
                error_info = ht_utils.ht_utils.get_general_error_message("FullTextSearchRetrieverQueueService",
                                                                         e)

                logger.error(f"Error in getting documents from Solr {error_info}")
                continue

            for record in result:
                item_id = record.ht_id
                logger.info(f"Processing document {item_id}")

                # publish the document in a queue
                item_metadata = record.metadata
                item_metadata['ht_id'] = item_id
                logger.info(f"Publishing document {item_id}")

                # Try to publish the document in the queue, if an error occurs, log the error and continue to the next
                # TODO: Add a mechanism to send the message to a dead letter queue
                try:
                    publish_document(queue_producer, item_metadata)

                    # Update the status of the item in a table
                    processed_items.append(item_id)
                except Exception as e:
                    error_info = ht_utils.ht_utils.get_error_message_by_document("FullTextSearchRetrieverQueueService",
                                                                                 e, item_metadata)

                    logger.error(f"Error in publishing document {item_id} {error_info}")
                    continue

            count_records += len(result)
            logger.info(f"Total of processed items {count_records}")

        non_processed_items = list(set(initial_documents) - set(processed_items))
        # TODO: Update the status of non processed items in a table
        logger.info(f"Total of non processed items {non_processed_items}")


def run_retriever_service(parallelize, num_threads, total_documents, list_documents, by_field, document_indexer_service,
                          start, rows):
    """
    Run the retriever service

    :param parallelize:
    :param num_threads:
    :param total_documents:
    :param list_documents:
    :param by_field:
    :param document_indexer_service:
    :param start:
    :param rows:
    """

    if parallelize:

        if num_threads:
            n_cores = num_threads
        else:
            n_cores = multiprocessing.cpu_count()

        if total_documents:
            batch_size = round(total_documents / n_cores + 0.5)
        else:
            logger.info("Nothing to process")
            return
        processes = [multiprocessing.Process(target=document_indexer_service.full_text_search_retriever_service,
                                             args=(list_documents[i:i + batch_size],
                                                   start, rows, by_field))
                     for i in range(0, total_documents, batch_size)]

        for process in processes:
            process.start()

        for process in processes:
            process.join()
    else:
        document_indexer_service.full_text_search_retriever_service(
            list_documents,
            start,
            rows,
            by_field
        )


def main():
    parser = argparse.ArgumentParser()

    init_args_obj = RetrieverServiceArguments(parser)

    # TODO: Use case: list_documents is None and query_field = record, that means rerun all the records in the Catalog
    if init_args_obj.list_documents is None and init_args_obj.query_field is None:
        logger.error("Error: `query` and `query fields` parameters required")
        sys.exit(1)

    document_indexer_service = FullTextSearchRetrieverQueueService(
        init_args_obj.solr_api_url,
        init_args_obj.queue_name,
        init_args_obj.queue_host,
        init_args_obj.queue_user,
        init_args_obj.queue_password,
        init_args_obj.dead_letter_queue)

    by_field = init_args_obj.query_field
    list_documents = init_args_obj.list_documents

    start_time = time.time()

    logger.info(f"Total of documents to process {len(list_documents)}")
    parallelize = True

    # TODO: Define the number of threads to use
    nthreads = None

    total_documents = len(list_documents)
    run_retriever_service(parallelize, nthreads, total_documents, list_documents, by_field, document_indexer_service,
                          init_args_obj.start, init_args_obj.rows)

    logger.info(f"Total time to retrieve and generate documents {time.time() - start_time:.10f}")


if __name__ == "__main__":
    main()
