from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ht_indexer_api.ht_indexer_api import HTSolrAPI


@pytest.fixture
def get_solr_api() -> HTSolrAPI:
    return HTSolrAPI("http://solr-lss-dev:8983/solr/core-x/")


@pytest.fixture
def get_fake_solr_api() -> HTSolrAPI:
    return HTSolrAPI("http://solr-lss-dev:8983/solr/core-not_exist/")


class TestHTSolrAPI:
    @patch("ht_indexer_api.ht_indexer_api.requests.get")
    def test_connection(self, mock_get: MagicMock, get_solr_api: HTSolrAPI) -> None:
        """
        Check if solr server is running. Mocks the HTTP call, not get_solr_status itself,
        so the method's own logic (which URL it hits) actually runs.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        solr_api_status = get_solr_api.get_solr_status()

        mock_get.assert_called_once_with(get_solr_api.url)
        assert solr_api_status.status_code == 200

    @patch("ht_indexer_api.ht_indexer_api.requests.post")
    def test_index_document_add(self, mock_post: MagicMock, get_solr_api: HTSolrAPI) -> None:
        """Mocks the HTTP call, not index_documents_by_file itself, so the method's own
        logic (reading the file, building the request) actually runs."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        document_path = Path(__file__).parents[2] / "src" / "ht_indexer_api" / "data" / "add"
        list_documents = ["39015078560292_solr_full_text.xml"]

        # Act
        response = get_solr_api.index_documents_by_file(
            document_path, list_documents=list_documents, solr_url_json="update/"
        )

        # Assert
        mock_post.assert_called_once()
        assert (
            mock_post.call_args.kwargs["data"] == (document_path / list_documents[0]).read_bytes()
        )
        assert response.status_code == 200
