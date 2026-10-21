from unittest.mock import MagicMock

import orjson
import pytest
import requests
from document_indexer_service.failure_classifier import FailureKind, classify_failure, failure_type
from pika.exceptions import AMQPConnectionError


def _http_error(status_code: int) -> requests.exceptions.HTTPError:
    return requests.exceptions.HTTPError(response=MagicMock(status_code=status_code))


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        # Solr unreachable or too slow
        (requests.exceptions.ConnectionError("refused"), FailureKind.TRANSIENT),
        (requests.exceptions.Timeout("slow"), FailureKind.TRANSIENT),
        (requests.exceptions.ConnectTimeout("slow"), FailureKind.TRANSIENT),
        # RabbitMQ trouble
        (AMQPConnectionError("broker down"), FailureKind.TRANSIENT),
        # Solr answered with a server error
        (_http_error(500), FailureKind.TRANSIENT),
        (_http_error(503), FailureKind.TRANSIENT),
        # Solr or a proxy says it is unavailable: never the document's fault
        (_http_error(429), FailureKind.TRANSIENT),
        (_http_error(502), FailureKind.TRANSIENT),
        (_http_error(504), FailureKind.TRANSIENT),
        # Bad document: verified against local Solr (unknown field -> 400, missing id -> 400)
        (_http_error(400), FailureKind.PERMANENT),
        (_http_error(422), FailureKind.PERMANENT),
        # Bad Solr credentials: verified against local Solr (no login -> 401)
        (_http_error(401), FailureKind.CONFIG_ERROR),
        (_http_error(403), FailureKind.CONFIG_ERROR),
        # Wrong Solr URL or missing core: needs a person to fix the configuration
        (_http_error(404), FailureKind.CONFIG_ERROR),
        # Document that cannot be serialized
        (orjson.JSONEncodeError("bad"), FailureKind.PERMANENT),
        # Unknown errors go to the (replayable) dead-letter queue
        (RuntimeError("???"), FailureKind.PERMANENT),
    ],
)
def test_classify_failure(exc: Exception, expected: FailureKind) -> None:
    assert classify_failure(exc) is expected


def test_http_error_without_a_response_is_permanent() -> None:
    assert classify_failure(requests.exceptions.HTTPError("no response")) is FailureKind.PERMANENT


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        # These labels appear in log lines that Loki alert rules match on: keep them stable.
        (_http_error(503), "http_503"),
        (_http_error(400), "http_400"),
        (_http_error(401), "http_401"),
        (requests.exceptions.HTTPError("no response"), "http_unknown"),
        (requests.exceptions.Timeout("slow"), "timeout"),
        (requests.exceptions.ReadTimeout("slow"), "timeout"),
        # ConnectTimeout is both a Timeout and a ConnectionError; "timeout" is the more useful label
        (requests.exceptions.ConnectTimeout("slow"), "timeout"),
        (requests.exceptions.ConnectionError("refused"), "connection"),
        (AMQPConnectionError("broker down"), "amqp"),
        (orjson.JSONEncodeError("bad"), "serialization"),
        (RuntimeError("???"), "unknown"),
    ],
)
def test_failure_type(exc: Exception, expected: str) -> None:
    assert failure_type(exc) == expected
