import os
from pathlib import Path

import pytest

from ht_indexer_api.ht_indexer_api import HTSolrAPI


@pytest.fixture
def get_solrAPI():
    return HTSolrAPI(
        url="http://solr-lss-dev:8983/solr/#/core-x/"
    )


@pytest.fixture
def get_fake_solrAPI():
    return HTSolrAPI(
        url="http://solr-lss-dev:8983/solr/#/core-not_exist/"
    )


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
        document_path = Path(f"{os.path.dirname(__file__)}/data/add")
        list_documents = ["39015078560292_solr_full_text.xml"]
        response = get_solrAPI.index_documents(document_path, list_documents=list_documents, solr_url_json="update/",
                                               headers={"Content-Type": "application/xml"})
        assert response.status_code == 200

    def test_query_by_id(self, get_solrAPI):
        """

        :param get_solrAPI:
        :return:
        """
        query = "oclc:23549320"
        response = get_solrAPI.get_documents(query=query, response_format="json")

        assert response.status_code == 200
        assert (
                response.headers["Content-Type"] == "text/plain;charset=utf-8"
        )

    def test_index_document_delete(self, get_solrAPI):
        document_path = Path(
            f"{os.path.dirname(__file__)}/data/delete"
        )  # "data/delete"
        list_documents = ["39015078560292-1-1-flat.solr_delete.xml"]
        response = get_solrAPI.index_documents(document_path, list_documents=list_documents, solr_url_json="update/",
                                               headers={"Content-Type": "application/xml"})
        assert response.status_code == 200

    def test_get_documents_failed(self, get_fake_solrAPI):
        query = "*:*"

        with pytest.raises(Exception, match=""):
            response = get_fake_solrAPI.get_documents(query, response_format="json")
