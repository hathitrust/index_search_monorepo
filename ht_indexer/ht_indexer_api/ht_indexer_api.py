import orjson
from pathlib import Path
from typing import Text

import requests
from requests.auth import HTTPBasicAuth

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class HTSolrAPI:
    def __init__(self, url, user=None, password=None):
        self.url = url
        self.auth = HTTPBasicAuth(user, password) if user and password else None

    def get_solr_status(self):
        response = requests.get(self.url)
        return response

    def index_document(self, xml_data: dict, content_type: Text = "application/json"):
        """Feed a JSON object, create an XML string to index the document into SOLR
        "Content-Type": "application/json"
        """
        try:
            response = requests.post(
                f"{self.url.replace('#/', '')}update/json/docs",
                headers={"Content-Type": content_type},
                json=xml_data,
                auth=self.auth,
                params={
                    "commit": "true",
                }, )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error in indexing document: {e}")
            raise e
        return response

    def index_documents(self, list_documents: list = None, solr_url_json: str = 'update/json/docs'):
        """Read an XML and feed into SOLR for indexing"""
        response = requests.post(
            f"{self.url.replace('#/', '')}{solr_url_json}",
            headers={"Content-Type": "application/json"},
            auth=self.auth,
            data=orjson.dumps(list_documents)
        )
        return response

    def index_documents_by_file(self, path: Path, list_documents: list = None, solr_url_json: str = 'update/json/docs'):
        """Read an XML and feed into SOLR for indexing"""
        data_path = Path(path)
        for doc in list_documents:
            doc_path = f"{data_path}/{doc}"
            doc_path = doc_path.replace(" ", "+")
            logger.info(f"Indexing {doc_path}")
            with open(doc_path, "rb") as xml_file:
                data_dict = xml_file.read()
                response = requests.post(
                    f"{self.url.replace('#/', '')}{solr_url_json}?commit=true",
                    headers={"Content-Type": "application/json"},
                    auth=self.auth,
                    data=data_dict,
                    params={
                        "commit": "true",
                    },
                )

        return response

    def send_solr_request(self, solr_host: str, solr_params: dict):
        """
        Send a request to Solr and return the response.
        """
        # try ... except block to catch any exception raised by the Solr connection
        try:
            response = requests.post(
                f"{solr_host}",
                params=solr_params,
                auth=self.auth,
                headers={"Content-type": "application/json"}
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.info(f"Error {e} in query: {solr_params}")
            raise e