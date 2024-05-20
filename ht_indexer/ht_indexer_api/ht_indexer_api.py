from pathlib import Path
from typing import Text

import requests

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class HTSolrAPI:
    def __init__(self, url):
        self.url = url

    def get_solr_status(self):
        response = requests.get(self.url)
        return response

    def index_document(self, xml_data: dict, content_type: Text = "application/json"):
        """Feed a JSON object, create an XML string to  index the document into SOLR
        "Content-Type": "application/json"
        """
        try:
            response = requests.post(
                f"{self.url.replace('#/', '')}update/json/docs",
                headers={"Content-Type": content_type},
                json=xml_data,
                params={
                    "commit": "true",
                }, )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error in indexing document: {e}")
            raise e
        return response

    def index_documents(self, path: Path, list_documents: list = None, solr_url_json: str = 'update/json/docs',
                        headers: dict = {"Content-Type": "application/json"}):
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
                    headers=headers,
                    data=data_dict,
                    params={
                        "commit": "true",
                    },
                )

        return response

    def get_documents(
            self,
            query: str = None,
            response_format: Text = "json",
            start: int = 0,
            rows: int = 100,
    ):
        """ Get documents from Solr server
        If solr server is running, it will return a response object
        otherwise, it will raise an exception
        Any exception will be raised to the caller
        """
        solr_headers = {"Content-type": "application/json"}

        if response_format == "xml":
            solr_headers = {"Content-type": "application/xml"}
        if response_format == "html":
            solr_headers = {"Content-type": "application/html"}

        data_query = {"q": "*:*"}
        if query:
            data_query["q"] = query
        else:
            data_query = {"q": "*:*"}

        data_query.update({"start": start, "rows": rows})

        try:
            response = requests.post(
                f"{self.url.replace('#/', '')}query",
                params=data_query,
                headers=solr_headers,
            )
            response.raise_for_status()
            logger.info(f"Executing query {query}.")
            return response
        except requests.exceptions.RequestException as e:
            logger.info(f"Error {e} in query: {query}")
            raise e
