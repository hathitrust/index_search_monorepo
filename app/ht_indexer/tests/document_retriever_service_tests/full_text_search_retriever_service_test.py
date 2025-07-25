import json

import pytest
from document_retriever_service.full_text_search_retriever_service import (
    FullTextSearchRetrieverQueueService,
)
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_queue_service.queue_consumer import QueueConsumer
from ht_utils.ht_logger import get_ht_logger
from ht_utils.query_maker import make_solr_term_query

logger = get_ht_logger(name=__name__)

@pytest.fixture
def get_catalog_retriever_service_solr_fake_solr_url():
    return HTSolrAPI("http://solr-sdr-catalog:9033/solr/catalogFake/", 'solr_user', 'solr_password')

@pytest.fixture
def get_solr_request(solr_catalog_url):
    return HTSolrAPI(solr_catalog_url, 'solr_user', 'solr_password')

@pytest.fixture

def get_document_retriever_service(solr_catalog_url, get_retriever_service_solr_parameters,
                                   get_rabbit_mq_host_name, random_queue_name):

    return FullTextSearchRetrieverQueueService(random_queue_name,
                                               get_rabbit_mq_host_name,
                                               "guest",
                                               "guest",
                                               solr_catalog_url,
                                               'solr_user',
                                                  'solr_password',
                                               get_retriever_service_solr_parameters
                                               )


class TestFullTextRetrieverService:

    def test_full_text_retriever_service_query(self):
        """Use case: Check if the Solr query is created correctly"""
        list_documents = ['nyp.33433082002258', 'not_exist_document']
        query = make_solr_term_query(list_documents, by_field="item")
        assert query == """{!terms f=ht_id}nyp.33433082002258,not_exist_document"""

    def test_full_text_service_retrieve_documents_from_solr(self, get_document_retriever_service, get_solr_request):
        """Use case: Check if the documents are retrieved from Solr"""
        list_documents = ['nyp.33433082002258', 'not_exist_document']

        query = make_solr_term_query(list_documents, by_field="item")

        response = get_document_retriever_service.retrieve_documents_from_solr(query,get_solr_request)

        output = json.loads(response.content.decode("utf-8"))
        assert output.get("response").get("numFound") == 1

    def test_generate_metadata(self, get_item_metadata):
        """Use case: Generate the metadata of the item to be indexed"""
        list_documents = ['mdp.39015078560292']

        metadata, item_id = FullTextSearchRetrieverQueueService.generate_metadata(get_item_metadata)

        assert metadata.get("ht_id") == list_documents[0]
        assert metadata.get('countryOfPubStr') == ['India']
        assert item_id == list_documents[0]

    def test_full_text_search_retriever_service(self, get_rabbit_mq_host_name,
                                                get_retriever_service_solr_parameters,
                                                solr_catalog_url):

        """ Use case: Check if the message is sent to the queue"""

        queue_name = "test_full_text_search_retriever_service"
        queue_user = "guest"
        queue_pass = "guest"
        # Define the consumer instance
        consumer_instance = QueueConsumer(
            queue_user,
            queue_pass,
            get_rabbit_mq_host_name,
            queue_name,
            False,
            1
        )

        # Clean up the queue
        consumer_instance.ht_channel.queue_purge(consumer_instance.queue_name)

        list_documents = ['nyp.33433082002258', 'not_exist_document']

        document_retriever_service_obj = FullTextSearchRetrieverQueueService(
            queue_name,
            get_rabbit_mq_host_name,
            queue_user,
            queue_pass,
            solr_catalog_url,
            "solr_user",
            "solr_password",
            get_retriever_service_solr_parameters
        )

        # Service to push a message
        document_retriever_service_obj.full_text_search_retriever_service(
            list_documents,
    "item"
        )

        #time.sleep(1) # Give RabbitMQ time to register the message

        # Service to consume the message
        for method_frame, properties, body in consumer_instance.consume_message(inactivity_timeout=5):

            if method_frame:
                output_message = json.loads(body.decode('utf-8'))
                assert output_message.get("ht_id") == list_documents[0]

                # Acknowledge the message if the message is processed successfully
                consumer_instance.positive_acknowledge(consumer_instance.ht_channel, method_frame.delivery_tag)
                break
            else:
                logger.info("The queue is empty: Test ended")
                break

        # Clean up the queue - To make sure the purge is done all the messages must be acknowledged
        consumer_instance.ht_channel.queue_purge(consumer_instance.queue_name)

    def test_retrieve_documents_by_item(self, get_solr_request, get_document_retriever_service):
        """Use case: Receive a list of items (ht_id) to index and retrieve the metadata from Catalog
        We want to index only the item that appear in the list and not all the items of each record.
        """
        list_documents = ['nyp.33433082002258', 'nyp.33433082046495', 'nyp.33433082046503', 'nyp.33433082046529',
                          'nyp.33433082046537', 'nyp.33433082046545', 'nyp.33433082067798', 'nyp.33433082067806',
                          'nyp.33433082067822']
        by_field = 'item'

        # Build the query to retrieve the total of documents to process
        query = make_solr_term_query(list_documents, by_field)

        # Retrieve the documents from Solr
        response = get_document_retriever_service.retrieve_documents_from_solr(query, get_solr_request)
        output = json.loads(response.content.decode("utf-8"))

        # Generate the metadata for the documents
        record_metadata_list = FullTextSearchRetrieverQueueService.generate_chunk_metadata(list_documents, output, by_field)

        assert len(record_metadata_list) == 9

    def test_retrieve_documents_by_record(self, get_solr_request,
                                          get_rabbit_mq_host_name,
                                          get_retriever_service_solr_parameters,
                                          solr_catalog_url,
                                          get_document_retriever_service):
        """Use case: Receive one record to process all their items"""

        list_documents = ["008394936"]
        by_field = 'record'

        # Build the query to retrieve the total of documents to process
        query = make_solr_term_query(list_documents, by_field)

        # Retrieve the documents from Solr
        response = get_document_retriever_service.retrieve_documents_from_solr(query, get_solr_request)
        output = json.loads(response.content.decode("utf-8"))

        # Generate the metadata for the documents
        record_metadata_list = FullTextSearchRetrieverQueueService.generate_chunk_metadata(list_documents, output, by_field)

        assert len(record_metadata_list) == 4

    def test_retrieve_documents_by_item_only_one(self, get_document_retriever_service, get_solr_request):
        """Use case: Retrieve only the metadata of the item given by parameter"""
        list_documents = ['nyp.33433082002258']
        by_field = 'item'

        # Build the query to retrieve the total of documents to process
        query = make_solr_term_query(list_documents, by_field)

        # Retrieve the documents from Solr
        response = get_document_retriever_service.retrieve_documents_from_solr(query, get_solr_request)
        output = json.loads(response.content.decode("utf-8"))

        # Generate the metadata for the documents
        record_metadata_list = FullTextSearchRetrieverQueueService.generate_chunk_metadata(list_documents, output, by_field)

        assert len(record_metadata_list) == 1

    def test_retrieve_documents_by_record_list_records(self, get_document_retriever_service, get_solr_request):
        """Use case: Receive one record to process all their items"""

        list_documents = ["008394936", "100393743"]
        by_field = 'record'

        # Build the query to retrieve the total of documents to process
        query = make_solr_term_query(list_documents, by_field)

        # Retrieve the documents from Solr
        response = get_document_retriever_service.retrieve_documents_from_solr(query, get_solr_request)
        output = json.loads(response.content.decode("utf-8"))

        # Generate the metadata for the documents
        record_metadata_list = FullTextSearchRetrieverQueueService.generate_chunk_metadata(list_documents, output, by_field)

        assert len(record_metadata_list) == 5

    def test_retrieve_documents_empty_result(self, get_document_retriever_service, get_solr_request):
        """Use case: Check of the results list is empty because the input item is not in Solr"""
        list_documents = ["this_id_does_not_exist_in_solr"]

        query = make_solr_term_query(list_documents, by_field="item")

        response = get_document_retriever_service.retrieve_documents_from_solr(query, get_solr_request)

        output = json.loads(response.content.decode("utf-8"))

        assert output.get("response").get("numFound") == 0


    def test_solr_is_not_working(self, get_catalog_retriever_service_solr_fake_solr_url):
        """Use case: Count the number of documents in Catalog"""

        list_documents = ['nyp.33433082002258']

        query = make_solr_term_query(list_documents, by_field="item")

        with pytest.raises(TypeError):
            response = FullTextSearchRetrieverQueueService.retrieve_documents_from_solr(query,
                                                                                    get_catalog_retriever_service_solr_fake_solr_url)
            assert response is None

