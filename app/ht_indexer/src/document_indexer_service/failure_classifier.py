import enum

import orjson
import requests
from pika.exceptions import AMQPError


class FailureKind(enum.Enum):
    """What a failure says about the message, and so what to do with it."""

    # Solr or RabbitMQ is having trouble; the message is fine. Keep it on the queue and retry.
    TRANSIENT = "transient"
    # The document itself is bad. Send it to the dead-letter queue.
    PERMANENT = "permanent"
    # Solr rejected our credentials, or the URL or core is wrong. Retrying won't help and it is
    # not the message's fault, so keep the message on the queue and make noise.
    CONFIG_ERROR = "config_error"


# 401/403: our login is refused. 404: wrong Solr URL or the core is missing. None of these go
# away without someone fixing the configuration, and none are the document's fault.
_CONFIG_ERROR_STATUS_CODES = {401, 403, 404}

# Solr, or a proxy in front of it, says it cannot take requests right now: too many requests,
# bad gateway, service unavailable, gateway timeout. This says nothing about the document, so
# these answers never count against a message's retries (see the 5xx note in classify_failure).
UNAVAILABLE_STATUS_CODES = {429, 502, 503, 504}


def classify_failure(exc: Exception) -> FailureKind:
    """Decide whether a failure while indexing is transient, permanent or a config error.

    Unknown exceptions are PERMANENT: the dead-letter queue can be replayed once the cause is
    fixed, whereas retrying a mystery error forever would block the queue.
    """
    if isinstance(exc, requests.exceptions.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        if status in _CONFIG_ERROR_STATUS_CODES:
            return FailureKind.CONFIG_ERROR
        if status in UNAVAILABLE_STATUS_CODES:
            return FailureKind.TRANSIENT
        # Solr sometimes answers 500 for a bad document (e.g. malformed JSON), so any other 5xx is
        # only "probably" transient; the per-message retry limit dead-letters it eventually.
        if status is not None and status >= 500:
            return FailureKind.TRANSIENT
        return FailureKind.PERMANENT

    # ConnectTimeout is both a ConnectionError and a Timeout; either way Solr is unreachable.
    if isinstance(exc, requests.exceptions.ConnectionError | requests.exceptions.Timeout):
        return FailureKind.TRANSIENT

    if isinstance(exc, AMQPError):
        return FailureKind.TRANSIENT

    # A document orjson cannot serialize will never succeed.
    if isinstance(exc, orjson.JSONEncodeError):
        return FailureKind.PERMANENT

    return FailureKind.PERMANENT


def failure_type(exc: Exception) -> str:
    """A short, stable label for the failure, used in log lines that alert rules match on.

    One of: http_<status> (e.g. http_503), http_unknown, timeout, connection, amqp,
    serialization, unknown. Do not rename these without checking the Loki alert rules.
    """
    if isinstance(exc, requests.exceptions.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        return f"http_{status}" if status is not None else "http_unknown"
    # Checked before ConnectionError: ConnectTimeout is both, and "timeout" is the more useful label.
    if isinstance(exc, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "connection"
    if isinstance(exc, AMQPError):
        return "amqp"
    if isinstance(exc, orjson.JSONEncodeError):
        return "serialization"
    return "unknown"
