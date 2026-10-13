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
    # Solr rejected our credentials. Retrying won't help and it is not the message's fault,
    # so keep the message on the queue and make noise.
    CONFIG_ERROR = "config_error"


_AUTH_STATUS_CODES = {401, 403}


def classify_failure(exc: Exception) -> FailureKind:
    """Decide whether a failure while indexing is transient, permanent or a config error.

    Unknown exceptions are PERMANENT: the dead-letter queue can be replayed once the cause is
    fixed, whereas retrying a mystery error forever would block the queue.
    """
    if isinstance(exc, requests.exceptions.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        if status in _AUTH_STATUS_CODES:
            return FailureKind.CONFIG_ERROR
        # Solr sometimes answers 500 for a bad document (e.g. malformed JSON), so a 5xx is only
        # "probably" transient; the per-message retry limit dead-letters it eventually.
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
