import pytest
import json

from document_retriever_service.full_text_search_retriever_service import FullTextSearchRetrieverQueueService
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_utils.query_maker import make_solr_term_query


@pytest.fixture
def get_catalog_retriever_service_solr_fake_solr_url():
    return HTSolrAPI("http://solr-sdr-catalog:9033/solr/catalogFake/", 'solr_user', 'solr_password')

@pytest.fixture
def get_solr_request(solr_catalog_url):
    return HTSolrAPI(solr_catalog_url, 'solr_user', 'solr_password')

@pytest.fixture
def get_document_retriever_service(solr_catalog_url, get_retriever_service_solr_parameters):
    return FullTextSearchRetrieverQueueService(
                                               "test_producer_queue",
                                               "rabbitmq",
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

    @pytest.mark.parametrize("retriever_parameters", [{"user": "guest", "password": "guest", "host": "rabbitmq",
                                                       "queue_name": "test_producer_queue",
                                                       "requeue_message": False,
                                                       "query_field": "item",
                                                       "batch_size": 1}])
    def test_full_text_search_retriever_service(self, retriever_parameters, get_document_retriever_service,
                                                consumer_instance):
        """ Use case: Check if the message is sent to the queue"""
        # Clean up the queue
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)

        list_documents = ['nyp.33433082002258', 'not_exist_document']

        get_document_retriever_service.full_text_search_retriever_service(
            list_documents,
            retriever_parameters["query_field"]
        )

        assert 1 == consumer_instance.conn.get_total_messages()

        # Clean up the queue
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)

    def test_retrieve_documents_by_item(self, get_document_retriever_service, get_solr_request):
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

    def test_retrieve_documents_by_record(self, get_document_retriever_service, get_solr_request):
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

        #results = get_catalog_retriever_service.retrieve_documents(list_documents, 0, 10, by_field)
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

        #results = get_catalog_retriever_service.retrieve_documents(list_documents, 0, 10, by_field)
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

        # results = get_catalog_retriever_service.retrieve_documents(list_documents, 0, 10, by_field)
        assert len(record_metadata_list) == 5

    def test_retrieve_documents_empty_result(self, get_document_retriever_service, get_solr_request):
        """Use case: Check of the results list is empty because the input item is not in Solr"""
        list_documents = ["this_id_does_not_exist_in_solr"]

        query = make_solr_term_query(list_documents, by_field="item")

        response = get_document_retriever_service.retrieve_documents_from_solr(query, get_solr_request)

        output = json.loads(response.content.decode("utf-8"))

        #results = get_catalog_retriever_service.retrieve_documents(list_documents, 0, 10, by_field)
        assert output.get("response").get("numFound") == 0


    def test_solr_is_not_working(self, get_catalog_retriever_service_solr_fake_solr_url):
        """Use case: Count the number of documents in Catalog"""

        list_documents = ['nyp.33433082002258']

        query = make_solr_term_query(list_documents, by_field="item")

        with pytest.raises(Exception):
            response = FullTextSearchRetrieverQueueService.retrieve_documents_from_solr(query,
                                                                                    get_catalog_retriever_service_solr_fake_solr_url)
            assert response is None

