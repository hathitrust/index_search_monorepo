import os

import pytest

from unittest.mock import MagicMock, patch
from pathlib import Path
from ht_indexer_api.ht_indexer_api import HTSolrAPI


@pytest.fixture
def get_solr_api():
    return HTSolrAPI(
        "http://solr-lss-dev:8983/solr/#/core-x/"
    )


@pytest.fixture
def get_fake_solr_api():
    return HTSolrAPI(
        "http://solr-lss-dev:8983/solr/#/core-not_exist/"
    )


class TestHTSolrAPI:

    @patch('ht_indexer_api.ht_indexer_api.HTSolrAPI.get_solr_status')
    def test_connection(self, mock_solr_status, get_solr_api):
        """
        Check if solr server is running
        :param get_solrAPI:
        :return:
        """
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_solr_status.return_value = mock_response

        solr_api_status = get_solr_api.get_solr_status()
        assert solr_api_status.status_code == 200

    @patch('ht_indexer_api.ht_indexer_api.HTSolrAPI.index_documents_by_file')
    def test_index_document_add(self, mock_index_documents, get_solr_api):
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_index_documents.return_value = mock_response

        document_path = Path(f"{os.path.dirname(__file__)}/data/add")
        list_documents = ["39015078560292_solr_full_text.xml"]

        # Act
        response = get_solr_api.index_documents_by_file(document_path, list_documents=list_documents,
                                                        solr_url_json="update/")

        # Assert
        assert response.status_code == 200

    @patch('ht_indexer_api.ht_indexer_api.HTSolrAPI.get_documents')
    def test_query_by_id(self, mock_get_documents, get_solr_api):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain;charset=utf-8"}

        mock_get_documents.return_value = mock_response

        """
        :param get_solrAPI:
        :return:
        """
        query = "oclc:23549320"
        response = get_solr_api.get_documents(query=query, response_format="json")

        assert response.status_code == 200
        assert (
                response.headers["Content-Type"] == "text/plain;charset=utf-8"
        )

    @patch('ht_indexer_api.ht_indexer_api.HTSolrAPI.index_documents_by_file')
    def test_index_document_delete(self, mock_index_documents, get_solr_api):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_index_documents.return_value = mock_response

        document_path = Path(
            f"{os.path.dirname(__file__)}/data/delete"
        )  # "data/delete"
        list_documents = ["39015078560292-1-1-flat.solr_delete.xml"]

        response = get_solr_api.index_documents_by_file(document_path, list_documents=list_documents, solr_url_json="update/")
        assert response.status_code == 200

    def test_get_documents_failed(self, get_fake_solr_api):
        query = "*:*"

        with pytest.raises(Exception, match=""):
            response = get_fake_solr_api.get_documents(query, response_format="json")
