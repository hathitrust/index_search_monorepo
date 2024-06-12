import pytest

from document_retriever_service.full_text_search_retriever_service import FullTextSearchRetrieverQueueService


@pytest.fixture
def get_document_retriever_service(solr_api_url):
    return FullTextSearchRetrieverQueueService(solr_api_url,
                                               "test_producer_queue",
                                               "rabbitmq",
                                               "guest",
                                               "guest"
                                               )


class TestFullTextRetrieverService:

    def test_full_text_service_count_documents(self, get_catalog_retriever_service):
        list_documents = ['nyp.33433082002258', 'not_exist_document']

        count_docs = FullTextSearchRetrieverQueueService.count_documents(get_catalog_retriever_service,
                                                                         list_documents,
                                                                         0,
                                                                         1,
                                                                         "item")

        assert 1 == count_docs

    def test_generate_metadata(self, get_item_metadata):
        list_documents = ['mdp.39015078560292']

        metadata, item_id = FullTextSearchRetrieverQueueService.generate_metadata(get_item_metadata)

        assert metadata.get("ht_id") == list_documents[0]
        assert metadata.get('countryOfPubStr') == ['India']
        assert item_id == list_documents[0]

    @pytest.mark.parametrize("retriever_parameters", [{"user": "guest", "password": "guest", "host": "rabbitmq",
                                                       "queue_name": "test_producer_queue",
                                                       "requeue_message": False,
                                                       "query_field": "item",
                                                       "start": 0,
                                                       "rows": 100}])
    def test_full_text_search_retriever_service(self, retriever_parameters, get_document_retriever_service,
                                                consumer_instance):
        # Clean up the queue
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)

        list_documents = ['nyp.33433082002258', 'not_exist_document']

        get_document_retriever_service.full_text_search_retriever_service(
            list_documents,
            retriever_parameters["start"],
            retriever_parameters["rows"],
            retriever_parameters["query_field"]
        )

        assert 1 == consumer_instance.conn.get_total_messages()

        # Clean up the queue
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)
