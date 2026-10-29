import socket
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from document_indexer_service.failure_classifier import FailureKind, classify_failure
from ht_indexer_api.ht_indexer_api import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_READ_TIMEOUT_SECONDS,
    HTSolrAPI,
)


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

        mock_get.assert_called_once_with(get_solr_api.url, timeout=get_solr_api.timeout)
        assert solr_api_status.status_code == 200

    @patch("ht_indexer_api.ht_indexer_api.requests.post")
    def test_index_document_add(self, mock_post: MagicMock, get_solr_api: HTSolrAPI) -> None:
        """Mocks the HTTP call, not index_documents_by_file itself, so the method's own
        logic (reading the file, building the request) actually runs."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        document_path = Path(__file__).parent / "data" / "add"
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


# --- Request timeout (ETT-1944) --------------------------------------------------------------

DOCUMENT_PATH = Path(__file__).parent / "data" / "add"
DOCUMENT_FILE = "39015078560292_solr_full_text.xml"

# Every way HTSolrAPI sends a request to Solr, with the requests function it uses
SOLR_CALLS: list[tuple[str, str, Callable[[HTSolrAPI], Any]]] = [
    ("get", "get_solr_status", lambda api: api.get_solr_status()),
    ("post", "index_document", lambda api: api.index_document({"id": "1"})),
    ("post", "index_documents", lambda api: api.index_documents([{"id": "1"}])),
    (
        "post",
        "index_documents_by_file",
        lambda api: api.index_documents_by_file(DOCUMENT_PATH, [DOCUMENT_FILE], "update/"),
    ),
    ("post", "send_solr_request", lambda api: api.send_solr_request("http://solr/q", {"q": "*"})),
]
CALL_IDS = [name for _, name, _ in SOLR_CALLS]


def test_default_timeouts() -> None:
    assert HTSolrAPI("http://solr/").timeout == (
        DEFAULT_CONNECT_TIMEOUT_SECONDS,
        DEFAULT_READ_TIMEOUT_SECONDS,
    )
    assert (DEFAULT_CONNECT_TIMEOUT_SECONDS, DEFAULT_READ_TIMEOUT_SECONDS) == (10.0, 120.0)


@pytest.mark.parametrize(("method", "name", "call"), SOLR_CALLS, ids=CALL_IDS)
def test_every_solr_request_uses_the_default_timeout(
    method: str, name: str, call: Callable[[HTSolrAPI], Any]
) -> None:
    with patch(f"ht_indexer_api.ht_indexer_api.requests.{method}") as mock_request:
        mock_request.return_value = MagicMock(status_code=200)
        call(HTSolrAPI("http://solr/"))

    assert mock_request.call_args.kwargs["timeout"] == (10.0, 120.0)


@pytest.mark.parametrize(("method", "name", "call"), SOLR_CALLS, ids=CALL_IDS)
def test_every_solr_request_uses_the_configured_timeout(
    method: str, name: str, call: Callable[[HTSolrAPI], Any]
) -> None:
    with patch(f"ht_indexer_api.ht_indexer_api.requests.{method}") as mock_request:
        mock_request.return_value = MagicMock(status_code=200)
        call(HTSolrAPI("http://solr/", read_timeout=30, connect_timeout=2))

    assert mock_request.call_args.kwargs["timeout"] == (2, 30)


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
@pytest.mark.parametrize("name", ["read_timeout", "connect_timeout"])
def test_a_timeout_that_is_not_positive_is_rejected(name: str, value: float) -> None:
    with pytest.raises(ValueError, match=f"{name} must be a finite number greater than 0"):
        if name == "read_timeout":
            HTSolrAPI("http://solr/", read_timeout=value)
        else:
            HTSolrAPI("http://solr/", connect_timeout=value)


@pytest.fixture
def silent_server() -> Generator[str]:
    """A local server that accepts connections and never answers, like a hung Solr."""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        yield f"http://127.0.0.1:{server.getsockname()[1]}/solr/core-x/"


def test_a_hung_solr_raises_a_timeout_that_the_indexer_treats_as_temporary(
    silent_server: str,
) -> None:
    """The setting really stops the wait, and the error is the one ETT-1894 keeps on the queue."""
    api = HTSolrAPI(silent_server, read_timeout=0.3)

    with pytest.raises(requests.exceptions.ReadTimeout) as error:
        api.index_documents([{"id": "mdp.1"}])

    assert classify_failure(error.value) is FailureKind.TRANSIENT
