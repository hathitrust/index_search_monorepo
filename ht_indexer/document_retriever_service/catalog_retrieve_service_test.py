import pytest

from document_retriever_service.catalog_retriever_service import CatalogRetrieverService


@pytest.fixture
def get_catalog_url():
    return "http://solr-sdr-catalog:9033/solr/#/catalog/"


@pytest.fixture
def get_catalog_retriever_service(get_catalog_url):
    return CatalogRetrieverService(get_catalog_url)


@pytest.fixture
def get_catalog_retriever_service_solr_fake_solr_url():
    return CatalogRetrieverService("http://solr-sdr-catalog:9033/solr/#/catalogFake/")


class TestCatalogRetrieverService:
    def test_retrieve_documents_by_item(self, get_catalog_retriever_service):
        """Use case: Receive a list of items to index and retrieve the metadata from Catalog"""
        list_documents = ['nyp.33433082002258', 'nyp.33433082046495', 'nyp.33433082046503', 'nyp.33433082046529',
                          'nyp.33433082046537', 'nyp.33433082046545', 'nyp.33433082067798', 'nyp.33433082067806',
                          'nyp.33433082067822']
        by_field = 'item'

        results = get_catalog_retriever_service.retrieve_documents(list_documents, 0, 10, by_field)
        assert len(results) == 9

    def test_retrieve_documents_by_record(self, get_catalog_retriever_service):
        """Use case: Receive one record to process all their items"""

        list_documents = ["008394936"]
        by_field = 'record'

        results = get_catalog_retriever_service.retrieve_documents(list_documents, 0, 10, by_field)
        assert len(results) == 4

    def test_retrieve_documents_by_item_only_one(self, get_catalog_retriever_service):
        """Use case: Receive a list of items to index and retrieve the metadata from Catalog"""
        list_documents = ['nyp.33433082002258']
        by_field = 'item'

        results = get_catalog_retriever_service.retrieve_documents(list_documents, 0, 10, by_field)
        assert len(results) == 1

    def test_retrieve_documents_by_record_list_records(self, get_catalog_retriever_service):
        """Use case: Receive one record to process all their items"""

        list_documents = ["008394936", "100393743"]
        by_field = 'record'

        results = get_catalog_retriever_service.retrieve_documents(list_documents, 0, 10, by_field)
        assert len(results) == 5

    def test_retrieve_documents_empty_result(self, get_catalog_retriever_service):
        """Use case: Receive a list of items to index and retrieve the metadata from Catalog"""
        list_documents = ["this_id_does_not_exist_in_solr"]
        by_field = 'item'

        results = get_catalog_retriever_service.retrieve_documents(list_documents, 0, 10, by_field)
        assert len(results) == 0

    def test_count_documents_zero_documents(self, get_catalog_retriever_service):
        """Test if the count_documents method returns 0 when the documents in the list are not in solr"""
        list_documents = ["this_id_does_not_exist_in_solr"]
        by_field = 'item'

        total_documents = get_catalog_retriever_service.count_documents(list_documents, 0, 10, by_field)
        assert total_documents == 0

    def test_count_documents_solr_is_not_working(self, get_catalog_retriever_service_solr_fake_solr_url):
        """Use case: Count the number of documents in Catalog"""
        list_documents = ['nyp.33433082002258']
        by_field = 'item'

        with pytest.raises(Exception):
            total_documents = get_catalog_retriever_service_solr_fake_solr_url.count_documents(list_documents,
                                                                                               0,
                                                                                               10,
                                                                                               by_field)
            assert total_documents is None
