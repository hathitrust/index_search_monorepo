import pytest
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from document_retrieval_service.document_retrieval_service import (
    DocumentRetrievalService,
)


@pytest.fixture()
def get_document_retrieval_service():
    solr_api = HTSolrAPI(url="http://solr-sdr-catalog:9033/solr/#/catalog/")

    document_retrieval_service = DocumentRetrievalService(solr_api)

    return document_retrieval_service


class TestDocumentRetrievalService:
    def test_get_records(self, get_document_retrieval_service):
        query = "ht_id:nyp.33433082046503"
        doc_metadata = get_document_retrieval_service.get_record_metadata(query)

        assert "nyp.33433082046503" in doc_metadata.get("content").get("response").get(
            "docs"
        )[0].get("ht_id")

    def test_create_entry(self, get_document_retrieval_service):
        """
        Test the function that creates the entry with fields retrieved from Catalog index
        :return:
        """

        query = "ht_id:nyp.33433082046503"
        doc_metadata = get_document_retrieval_service.get_record_metadata(query)

        assert "nyp.33433082046503" in doc_metadata.get("content").get("response").get(
            "docs"
        )[0].get("ht_id")
