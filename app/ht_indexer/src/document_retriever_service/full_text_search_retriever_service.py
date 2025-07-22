import argparse
import copy
import inspect
import json
import multiprocessing
import os
import sys
import time

import requests
from catalog_metadata.catalog_metadata import CatalogItemMetadata, CatalogRecordMetadata
from document_generator.ht_mysql import get_mysql_conn
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_indexer_monitoring.ht_indexer_tracktable import (
    HT_INDEXER_TRACKTABLE,
    PROCESSING_STATUS_TABLE_NAME,
)
from ht_queue_service.queue_connection import MAX_DOCUMENT_IN_QUEUE
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import (
    get_current_time,
    get_error_message_by_document,
    get_general_error_message,
    split_into_batches,
)
from ht_utils.query_maker import make_solr_term_query

from document_retriever_service.retriever_arguments import RetrieverServiceArguments
from document_retriever_service.retriever_services_utils import RetrieverServicesUtils

logger = get_ht_logger(name=__name__)

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

PROCESSES = multiprocessing.cpu_count() - 1
WAITING_TIME_QUEUE_PRODUCER = 180 # Wait 3 minutes to send documents in the queue
WAITING_TIME_MYSQL = 60 # Wait 1 minute to query MySQL checking if there are documents to process (retriever_status = pending)
MYSQL_COLUMN_UPDATE = 'retriever_status'
SUCCESS_UPDATE_STATUS = f"UPDATE {PROCESSING_STATUS_TABLE_NAME} SET status = %s, {MYSQL_COLUMN_UPDATE} = %s, processed_at = %s WHERE ht_id = %s"
FAILURE_UPDATE_STATUS = f"UPDATE {PROCESSING_STATUS_TABLE_NAME} SET status = %s, {MYSQL_COLUMN_UPDATE} = %s, processed_at = %s, error = %s WHERE ht_id = %s"
PARALLELIZE = True
SOLR_BATCH_SIZE = 200 # The chunk size is 200, because Solr will fail with the status code 414. The chunk size was determined
# by testing the Solr query with different values (e.g., 100-500 and with 200 ht_ids it worked.

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

    def __init__(self, queue_name: str = 'retriever_queue', queue_host: str = None,
                 queue_user: str = None,
                 queue_password: str = None,
                 solr_host: str = None,
                 solr_user: str = None,
                 solr_password: str = None,
                 solr_retriever_query_params: dict = None
                 ):


        self.queue_name = queue_name
        self.queue_host = queue_host
        self.queue_user = queue_user
        self.queue_password = queue_password
        self.solr_host = solr_host
        self.solr_user = solr_user
        self.solr_password = solr_password
        self.solr_retriever_query_params = solr_retriever_query_params


    def get_queue_producer(self) -> QueueProducer | None:

        """Establish a connection to the queue to publish the documents"""

        try:
            queue_producer = QueueProducer(self.queue_user, self.queue_password, self.queue_host, self.queue_name)
            return queue_producer
        except Exception as e:
            logger.error(f"Environment variables required: "
                         f"{get_general_error_message('DocumentGeneratorService', e)}")



    @staticmethod
    def generate_metadata(record: CatalogItemMetadata) -> tuple[dict, str]:

        """ Generate the metadata and the ht_id of the document to be published in the queue"""

        item_id = record.ht_id
        logger.info(f"Processing document {item_id}")

        item_metadata = record.metadata
        item_metadata['ht_id'] = item_id

        return item_metadata, item_id

    @staticmethod
    def publishing_documents(queue_producer, result, mysql_db):

        processed_items = []
        failed_items = []

        for record in result:

            item_metadata, item_id = FullTextSearchRetrieverQueueService.generate_metadata(record)
            logger.info(f"Publishing document {item_id}")

            # Try to publish the document in the queue, if an error occurs, log the error and continue to the next
            try:
                RetrieverServicesUtils.publish_document(queue_producer, item_metadata)
                processed_items.append(('processing', 'completed', get_current_time(), item_id))

            except Exception as e:
                error_info = get_error_message_by_document("FullTextSearchRetrieverQueueService",
                                                                             e, item_metadata)

                failed_items.append(('failed', 'failed', get_current_time(),
                                    f"{error_info.get('service_name')}_{error_info.get('error_message')}",
                                     error_info.get('ht_id')))

                logger.error(f"Error in publishing document {item_id} {error_info}")
                continue

        # Update the status of the items in MySQL table
        if len(failed_items)>0:
            mysql_db.update_status(FAILURE_UPDATE_STATUS, failed_items)

        if len(processed_items)>0:
            logger.info(f"Total of processed documents: {len(processed_items)}")
            mysql_db.update_status(SUCCESS_UPDATE_STATUS, processed_items)

    def retrieve_documents_from_solr(self, solr_query: str, solr_retriever) -> requests.Response:

        """Function to retrieve documents from Solr
        :param solr_query:
        :param solr_retriever: HTSolrAPI object
        :return: response from Solr
        """

        chunk_solr_params = copy.deepcopy(self.solr_retriever_query_params)

        chunk_solr_params['fq'] = solr_query

        response = solr_retriever.send_solr_request(
            solr_host=f"{self.solr_host}/query",
            solr_params=chunk_solr_params
        )
        if response.status_code != 200:
            logger.error(f"Error {response.status_code} in query: {solr_query}")
            raise requests.exceptions.RequestException(f"Error {response.status_code} in query: {solr_query}")
        return response

    @staticmethod
    def generate_chunk_metadata(chunk: list, solr_output: dict, by_field: str = 'item') -> list[
                                                                                               CatalogItemMetadata] | None:
        """Generate the metadata for the documents

        :param chunk: list of documents to process
        :param solr_output: response from Solr
        :param by_field: field to search by (item=ht_id or record=id)
        :return: list of metadata for the documents
        """

        record_metadata_list = []
        for record in solr_output.get("response").get("docs"):

            # Create the object to create items and metadata.
            catalog_record_metadata = CatalogRecordMetadata(record)

            # If there is something with Solr retrieving a chunk of documents will try to retrieve the next chunk
            try:
                if by_field == 'item':
                    # Validate query field = ht_id, list_documents could contain 1 or more items, but they probably are from
                    # different records
                    # Process a specific item of a record
                    results = RetrieverServicesUtils.create_catalog_object_by_item_id(chunk, record, catalog_record_metadata)
                    # This is the most efficient way to retrieve the items from Catalog
                else:
                    # Process all the items of a record
                    results = RetrieverServicesUtils.create_catalog_object_by_record_id(record, catalog_record_metadata)

                record_metadata_list.extend(results)
            except Exception as e:
                error_info = get_general_error_message("FullTextSearchRetrieverQueueService",
                                                                         e)
                logger.error(f"Error in getting documents from Solr {error_info}")
        return record_metadata_list

    def full_text_search_retriever_service(self, initial_documents, by_field: str = 'item'):
        """
        This method is used to retrieve the documents from the Catalog and generate the full text search entry
        If the Solr is not available, an error will be raised, and the process will be stopped

        We run Solr queries in batch
        Each batch will retrieve 200 documents because Solr will fail with the status code 414
        if the URI is too Long.
        """

        # Create a connection to the MySQL database
        mysql_db = get_mysql_conn(pool_size=1)

        # Create a connection to the queue to produce messages
        queue_producer = self.get_queue_producer()

        solr_retriever = HTSolrAPI(self.solr_host, self.solr_user, self.solr_password)

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
            record_metadata_list = FullTextSearchRetrieverQueueService.generate_chunk_metadata(chunk, output, by_field)

            logger.info(f"Metadata generator: Total items = {len(record_metadata_list)}.")
            logger.info(f"Metadata generator: Total time = {time.time() - start_time}")

            # Publish the documents in the queue
            FullTextSearchRetrieverQueueService.publishing_documents(queue_producer, record_metadata_list, mysql_db)


def run_retriever_service(list_documents, by_field, document_retriever_service, parallelize: bool = False):
    """
    Run the retriever service

    :param list_documents:
    :param by_field:
    :param document_retriever_service:
    :param parallelize: if True, the process will run in parallel
    """

    total_documents = len(list_documents)

    if parallelize:

        n_cores = multiprocessing.cpu_count()

        # The number of MySQL connections is equal to batch_size
        if total_documents > 0:
            batch_size = round(total_documents / n_cores + 0.5)
        else:
            logger.info("Nothing to process")
            return

        start_time = time.time()

        processes = [multiprocessing.Process(target=document_retriever_service.full_text_search_retriever_service,
                                             args=(list_documents[i:i + batch_size],
                                                   by_field))
                     for i in range(0, total_documents, batch_size)]

        for process in processes:
            process.start()

        for process in processes:
            process.join()

        logger.info(f"Process=retrieving: Total time to retrieve a batch documents {time.time() - start_time:.10f}")

    else:
        document_retriever_service.full_text_search_retriever_service(
            list_documents,
            by_field
        )

def main():
    parser = argparse.ArgumentParser()

    init_args_obj = RetrieverServiceArguments(parser)

    # TODO: Use case: list_documents is None and query_field = record, that means rerun all the records in the Catalog
    if init_args_obj.list_documents is None and init_args_obj.query_field is None:
        logger.error("Error: `query` and `query fields` parameters required")
        sys.exit(1)

    document_retriever_service = FullTextSearchRetrieverQueueService(
        init_args_obj.queue_name,
        init_args_obj.queue_host,
        init_args_obj.queue_user,
        init_args_obj.queue_password,
    init_args_obj.solr_host,
    init_args_obj.solr_user,
    init_args_obj.solr_password,
    init_args_obj.solr_retriever_query_params
    )

    # by_field is use to define the type of query to retrieve the documents (by item or by record).
    # From MySQL table we will always return the ht_id and record_id
    # To retrieve documents from Catalog the field is used to define the type of query

    by_field = init_args_obj.query_field

    if len(init_args_obj.list_documents) > 0:

        # If the list of documents is provided, the process will run only for the documents in the list
        list_ids = RetrieverServicesUtils.extract_ids_from_documents(init_args_obj.list_documents, by_field)
        logger.info(f"Process=retrieving: Total of documents to process {len(list_ids)}")
        run_retriever_service(list_ids, by_field, document_retriever_service, parallelize=PARALLELIZE)
    else:

        # If the table does not exist, stop the process
        if not init_args_obj.db_conn.table_exists(PROCESSING_STATUS_TABLE_NAME):
            logger.error(f"{PROCESSING_STATUS_TABLE_NAME} does not exist")
            init_args_obj.db_conn.create_table(HT_INDEXER_TRACKTABLE)

        # The process will run every 5 minutes to check if there are documents to process (retriever_status = pending)
        while True:
            total_time_waiting = 0
            if total_time_waiting > 0:
                logger.info(f"Process=retrieving: Waiting {total_time_waiting} until reduce the number of messages in the queue")
            list_documents = init_args_obj.db_conn.query_mysql(init_args_obj.retriever_query)
            if len(list_documents) == 0:
                logger.info("No documents to process")
                time.sleep(WAITING_TIME_MYSQL)
                continue
            else:
                list_ids = RetrieverServicesUtils.extract_ids_from_documents(list_documents, by_field)

            logger.info(f"Process=retrieving: Total of documents to process {len(list_ids)}")

            run_retriever_service(list_ids, by_field, document_retriever_service, parallelize=PARALLELIZE)

            # Checking the number of messages in the queue
            # Create a connection to the queue to produce messages
            queue_producer = document_retriever_service.get_queue_producer()

            total_messages_in_queue = queue_producer.get_total_messages()

            while total_messages_in_queue > MAX_DOCUMENT_IN_QUEUE:
                logger.info (f"Waiting: There are {total_messages_in_queue} or more documents in the {queue_producer.queue_name}")
                time.sleep(WAITING_TIME_QUEUE_PRODUCER) # Wait 5 minutes to send documents in the queue
                total_messages_in_queue = queue_producer.get_total_messages()
                total_time_waiting += WAITING_TIME_QUEUE_PRODUCER
            queue_producer.close()


if __name__ == "__main__":
    main()
