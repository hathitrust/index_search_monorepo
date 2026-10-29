from pathlib import Path
from typing import Any

import orjson
import requests
from ht_utils.ht_logger import get_ht_logger
from requests.auth import HTTPBasicAuth

logger = get_ht_logger(name=__name__)

# Seconds to wait for Solr to accept the connection.
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10.0
# Seconds to wait for Solr to send data. It is the longest silence allowed between bytes, not a limit
# on the whole request, so a slow batch that keeps sending data does not hit it.
DEFAULT_READ_TIMEOUT_SECONDS = 120.0


class HTSolrAPI:
    def __init__(
        self,
        url: str,
        user: str | None = None,
        password: str | None = None,
        read_timeout: float = DEFAULT_READ_TIMEOUT_SECONDS,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    ):
        """
        :param url: The Solr URL
        :param user: Solr user, for basic authentication
        :param password: Solr password, for basic authentication
        :param read_timeout: Seconds to wait for Solr to send data before the request fails
        with a requests.exceptions.Timeout. Applies to every request to Solr.
        :param connect_timeout: Seconds to wait for Solr to accept the connection
        :raises ValueError: If a timeout is not greater than zero (requests would wait forever
        for None and rejects 0)
        """
        for name, value in (("read_timeout", read_timeout), ("connect_timeout", connect_timeout)):
            if not value > 0:
                raise ValueError(f"{name} must be greater than 0 seconds, got {value}")
        self.url = url
        self.auth = HTTPBasicAuth(user, password) if user and password else None
        self.timeout = (connect_timeout, read_timeout)

    def get_solr_status(self) -> requests.Response:
        response = requests.get(self.url, timeout=self.timeout)
        return response

    def index_document(
        self, xml_data: dict[str, Any], content_type: str = "application/json"
    ) -> requests.Response:
        """Feed a JSON object, create an XML string to index the document into SOLR
        "Content-Type": "application/json"
        """
        try:
            response = requests.post(
                f"{self.url.replace('#/', '')}update/json/docs",
                headers={"Content-Type": content_type},
                json=xml_data,
                auth=self.auth,
                timeout=self.timeout,
                params={
                    "commit": "true",
                },
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error in indexing document: {e}")
            raise e
        return response

    def index_documents(
        self, list_documents: list[dict[str, Any]], solr_url_json: str = "update/json/docs"
    ) -> requests.Response:
        """Read an XML and feed into SOLR for indexing"""
        response = requests.post(
            f"{self.url.replace('#/', '')}{solr_url_json}",
            headers={"Content-Type": "application/json"},
            auth=self.auth,
            timeout=self.timeout,
            data=orjson.dumps(list_documents),
        )
        return response

    def index_documents_by_file(
        self, path: str | Path, list_documents: list[str], solr_url_json: str = "update/json/docs"
    ) -> requests.Response:
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
                    timeout=self.timeout,
                    data=data_dict,
                    params={
                        "commit": "true",
                    },
                )

        # FIXME only returns last response; will miss errors from earlier
        # responses should consider checking for exceptions after the post
        # rather than expecting the caller to check
        return response

    def send_solr_request(self, solr_host: str, solr_params: dict[str, Any]) -> requests.Response:
        """
        Send a request to Solr and return the response.
        """
        # try ... except block to catch any exception raised by the Solr connection
        try:
            response = requests.post(
                f"{solr_host}",
                params=solr_params,
                auth=self.auth,
                timeout=self.timeout,
                headers={"Content-type": "application/json"},
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.info(f"Error {e} in query: {solr_params}")
            raise e
