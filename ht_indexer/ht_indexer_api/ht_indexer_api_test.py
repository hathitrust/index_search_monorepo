import pytest

from ht_indexer_api.ht_indexer_api import HTSolrAPI


@pytest.fixture
def get_solrAPI():
    return HTSolrAPI(
        url="http://solr-lss-dev:8983/solr/#/core-x/"
    )  # http://localhost:9033/solr/#/catalog/

class TestHTSolrAPI:
    def test_connection(self, get_solrAPI):
        """
        Check if solr server is running
        :param get_solrAPI:
        :return:
        """
        solr_api_status = get_solrAPI.get_solr_status()
        assert solr_api_status.status_code == 200

    def test_index_document_add(self, get_solrAPI):
        document_path = "data/add"
        response = get_solrAPI.index_document(document_path)
        assert response.status_code == 200

    def test_query_by_id(self, get_solrAPI):
        """

        :param get_solrAPI:
        :return:
        """
        query = "oclc:23549320"
        response = get_solrAPI.get_documents(query=query, response_format="json")

        assert response.status_code == 200
        assert response.headers["Content-Type"] == "text/plain;charset=utf-8"  # "application/json;charset=utf-8"

    def test_index_document_delete(self, get_solrAPI):
        document_path = "data/delete"
        response = get_solrAPI.index_document(document_path)
        assert response.status_code == 200
