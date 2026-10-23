import time
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from document_indexer_service.document_indexer_service import DocumentIndexerQueueService
from ht_utils.ht_logger import get_ht_logger
from ht_utils.testing import assert_log_entry, capture_logs, find_log_entry


@pytest.fixture(autouse=True)
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record the backoff waits instead of really sleeping."""
    recorded: list[float] = []
    monkeypatch.setattr(time, "sleep", recorded.append)
    return recorded


def _make_service(solr_api_full_text: MagicMock) -> tuple[DocumentIndexerQueueService, MagicMock]:
    """DocumentIndexerQueueService.__init__ connects to a live RabbitMQ broker via its
    parent class, which isn't needed to exercise process_batch's own logic. Build the
    instance without running __init__ and set only what process_batch actually touches.
    Returns the channel mock separately (typed as MagicMock, not BlockingChannel | None)
    so tests can assert on it without a None-narrowing check.
    """
    service = DocumentIndexerQueueService.__new__(DocumentIndexerQueueService)
    service.solr_api_full_text = solr_api_full_text
    channel = MagicMock()
    service.channel = channel
    service.queue_manager = MagicMock(dead_letter_queue_name="dlq_name")
    service.requeue_message = False
    service.max_retries = 5
    service.retry_attempts = {}
    service.retried_in_batch = 0
    service.consecutive_retry_batches = 0
    service.logger = get_ht_logger("indexer_test").bind()
    return service, channel


# list of solr documents
def _batch() -> list[dict[str, Any]]:
    return [{"id": "test.item1"}, {"id": "test.item2"}]


def _http_error(status_code: int) -> requests.exceptions.HTTPError:
    return requests.exceptions.HTTPError(response=MagicMock(status_code=status_code))


def _ok_response() -> MagicMock:
    return MagicMock(status_code=200)


def _error_response(status_code: int) -> MagicMock:
    """A Solr response whose raise_for_status() raises, like requests does for 4xx/5xx."""
    response = MagicMock(status_code=status_code)
    response.raise_for_status.side_effect = _http_error(status_code)
    return response


def _acked_tags(channel: MagicMock) -> list[int]:
    return [call.kwargs["delivery_tag"] for call in channel.basic_ack.call_args_list]


def _retried_tags(channel: MagicMock) -> list[int]:
    return [call.kwargs["delivery_tag"] for call in channel.basic_nack.call_args_list]


def _dead_lettered_tags(channel: MagicMock) -> list[int]:
    return [call.kwargs["delivery_tag"] for call in channel.basic_reject.call_args_list]


def test_process_batch_returns_true_and_acks_on_success() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _ok_response()
    service, channel = _make_service(solr_api_full_text)
    batch = _batch()
    delivery_tags = [10, 11]

    result = service.process_batch(batch, delivery_tags)

    assert result is True
    assert channel.basic_ack.call_count == 2
    assert batch == []
    assert delivery_tags == []


def test_process_batch_acks_good_documents_and_dead_letters_only_the_bad_one() -> None:
    """Acceptance criterion: a batch of 3 with 1 bad document leads to 2 acks and 1 reject."""

    def index_documents(documents: list[dict[str, Any]]) -> MagicMock:
        # Like Solr: a request containing the bad document fails with 400.
        if any(doc.get("bad") for doc in documents):
            return _error_response(400)
        return _ok_response()

    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = index_documents
    service, channel = _make_service(solr_api_full_text)
    batch: list[dict[str, Any]] = [{"id": "1"}, {"id": "2", "bad": True}, {"id": "3"}]
    delivery_tags = [10, 11, 12]

    result = service.process_batch(batch, delivery_tags)

    assert result is False
    assert _acked_tags(channel) == [10, 12]
    assert _dead_lettered_tags(channel) == [11]
    assert channel.basic_reject.call_args.kwargs["requeue"] is False
    assert channel.basic_nack.call_count == 0
    assert batch == []
    assert delivery_tags == []


def test_process_batch_keeps_messages_on_queue_when_solr_is_unreachable() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = requests.exceptions.ConnectionError("refused")
    service, channel = _make_service(solr_api_full_text)
    batch = _batch()
    delivery_tags = [10, 11]

    result = service.process_batch(batch, delivery_tags)

    assert result is False
    assert _retried_tags(channel) == [10, 11]
    assert channel.basic_reject.call_count == 0
    assert channel.basic_ack.call_count == 0
    # One request for the batch; per-document retries would fail the same way.
    assert solr_api_full_text.index_documents.call_count == 1
    assert batch == []
    assert delivery_tags == []


def test_process_batch_keeps_messages_on_queue_when_solr_rejects_credentials() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _error_response(401)
    service, channel = _make_service(solr_api_full_text)

    result = service.process_batch(_batch(), [10, 11])

    assert result is False
    assert _retried_tags(channel) == [10, 11]
    assert channel.basic_reject.call_count == 0
    assert solr_api_full_text.index_documents.call_count == 1


def test_process_batch_retries_documents_one_by_one_when_solr_answers_with_a_server_error() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _error_response(500)
    service, channel = _make_service(solr_api_full_text)

    result = service.process_batch(_batch(), [10, 11])

    assert result is False
    # 1 request for the batch + 1 per document; a 5xx might be caused by a single document.
    assert solr_api_full_text.index_documents.call_count == 3
    assert _retried_tags(channel) == [10, 11]
    assert channel.basic_reject.call_count == 0


def test_process_batch_acks_everything_when_the_server_error_was_momentary() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = [
        _error_response(500),
        _ok_response(),
        _ok_response(),
    ]
    service, channel = _make_service(solr_api_full_text)

    result = service.process_batch(_batch(), [10, 11])

    assert result is True
    assert _acked_tags(channel) == [10, 11]
    assert channel.basic_nack.call_count == 0
    assert channel.basic_reject.call_count == 0


def test_process_batch_stops_posting_when_solr_goes_down_during_the_one_by_one_retry() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = [
        _error_response(400),  # the batch
        _ok_response(),  # document 1
        requests.exceptions.ConnectionError("refused"),  # document 2
    ]
    service, channel = _make_service(solr_api_full_text)
    batch = [{"id": "1"}, {"id": "2"}, {"id": "3"}]

    result = service.process_batch(batch, [10, 11, 12])

    assert result is False
    assert _acked_tags(channel) == [10]
    assert _retried_tags(channel) == [11, 12]
    assert channel.basic_reject.call_count == 0
    # Document 3 was not posted: Solr had just stopped answering.
    assert solr_api_full_text.index_documents.call_count == 3


def test_process_batch_dead_letters_a_document_that_fails_with_an_unknown_error() -> None:
    """Unknown errors are treated as the document's fault. The dead-letter queue is replayable."""
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = RuntimeError("???")
    service, channel = _make_service(solr_api_full_text)

    result = service.process_batch(_batch(), [10, 11])

    assert result is False
    assert _dead_lettered_tags(channel) == [10, 11]
    assert channel.basic_nack.call_count == 0


# --- Bounded retry and backoff ---------------------------------------------------------------


def test_message_that_keeps_getting_a_server_error_is_dead_lettered_after_max_retries() -> None:
    """A poison message cannot be put back forever (ETT-1894)."""
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _error_response(500)
    service, channel = _make_service(solr_api_full_text)
    service.max_retries = 2

    # The queue hands the same message back each time, with a new delivery tag.
    for delivery_tag in (10, 11, 12):
        service.process_batch([{"id": "1"}], [delivery_tag])

    assert _retried_tags(channel) == [10, 11]
    assert _dead_lettered_tags(channel) == [12]
    # Its count is cleared once it has left the queue.
    assert service.retry_attempts == {}


def test_outage_never_uses_up_a_messages_retries() -> None:
    """Good messages must survive any outage: being unreachable is not the message's fault."""
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = requests.exceptions.ConnectionError("refused")
    service, channel = _make_service(solr_api_full_text)
    service.max_retries = 2

    for delivery_tag in range(10, 20):
        service.process_batch([{"id": "1"}], [delivery_tag])

    assert len(_retried_tags(channel)) == 10
    assert channel.basic_reject.call_count == 0
    assert service.retry_attempts == {}


def test_retry_count_is_cleared_when_the_message_is_finally_indexed() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = [
        _error_response(500),  # batch
        _error_response(500),  # the document alone
        _ok_response(),  # next delivery
    ]
    service, channel = _make_service(solr_api_full_text)

    service.process_batch([{"id": "1"}], [10])
    assert service.retry_attempts == {"1": 1}
    service.process_batch([{"id": "1"}], [11])

    assert service.retry_attempts == {}
    assert _acked_tags(channel) == [11]


def test_backoff_doubles_while_batches_keep_failing_and_resets_after_a_clean_one(
    sleeps: list[float],
) -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = [
        requests.exceptions.ConnectionError("refused"),
        requests.exceptions.ConnectionError("refused"),
        requests.exceptions.ConnectionError("refused"),
        _ok_response(),  # Solr is back
        requests.exceptions.ConnectionError("refused"),
    ]
    service, _ = _make_service(solr_api_full_text)

    for delivery_tag in range(5):
        service.process_batch([{"id": str(delivery_tag)}], [delivery_tag])

    assert sleeps == [1.0, 2.0, 4.0, 1.0]


def test_backoff_is_capped(sleeps: list[float]) -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = requests.exceptions.ConnectionError("refused")
    service, _ = _make_service(solr_api_full_text)
    # A very long outage: 2 ** 1000 would overflow a float if the exponent were not limited
    service.consecutive_retry_batches = 1000

    service.process_batch([{"id": "1"}], [10])

    assert sleeps == [60.0]


def test_no_backoff_when_nothing_was_put_back(sleeps: list[float]) -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = [
        _error_response(400),  # batch with a bad document
        _error_response(400),  # the bad document alone: dead-lettered, not put back
    ]
    service, _ = _make_service(solr_api_full_text)

    service.process_batch([{"id": "1"}], [10])

    assert sleeps == []


# --- Structured log lines (alert contract) ---------------------------------------------------
# Loki alert rules match on these lines. If one of these tests has to change, the alert rules
# need to change with it.


def test_process_batch_logs_indexed_document_ids() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = MagicMock(status_code=200)
    service, channel = _make_service(solr_api_full_text)
    batch = _batch()
    delivery_tags = [10, 11]

    with capture_logs() as entries:
        service.process_batch(batch, delivery_tags)

        assert_log_entry(entries, ht_id="test.item1", event="document_indexed")
        assert_log_entry(entries, ht_id="test.item2", event="document_indexed")


def test_rejected_batch_does_not_log_document_indexed() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = requests.exceptions.ConnectionError("refused")
    service, _ = _make_service(solr_api_full_text)
    batch = _batch()
    delivery_tags = [10, 11]

    with capture_logs() as entries:
        service.process_batch(batch, delivery_tags)

        assert not any(entry["event"] == "document_indexed" for entry in entries)


def test_success_is_logged_as_documents_indexed() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _ok_response()
    service, _ = _make_service(solr_api_full_text)

    with capture_logs() as entries:
        service.process_batch(_batch(), [10, 11])

        entry = find_log_entry(entries, event="batch_indexed", item_count=2, http_status=200)

        assert entry is not None
        assert entry["seconds"] is not None


def test_solr_outage_is_logged_as_a_transient_solr_request_failure() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = requests.exceptions.ConnectionError("refused")
    service, _ = _make_service(solr_api_full_text)

    with capture_logs() as entries:
        service.process_batch(_batch(), [10, 11])

        assert_log_entry(
            entries,
            event="message_retried",
            ht_id="test.item1",
            failure_kind="transient",
            error="refused",
        )
        assert not any(entry["event"] == "message_dead_lettered" for entry in entries)


def test_bad_document_is_logged_as_permanent_and_dead_lettered() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _error_response(400)
    service, _ = _make_service(solr_api_full_text)

    with capture_logs() as entries:
        service.process_batch([{"id": "test.always_bad"}], [10])

        failures = [e for e in entries if e["event"] == "solr_request_failed"]

        assert len(failures) == 2
        assert_log_entry(
            failures,
            event="solr_request_failed",
            scope="batch",
            docs=1,
            failure_kind="permanent",
            failure_type="http_400",
        )

        assert_log_entry(
            failures,
            event="solr_request_failed",
            scope="document",
            docs=1,
            failure_kind="permanent",
            failure_type="http_400",
        )

        specific_error = find_log_entry(
            entries,
            event="message_dead_lettered",
            ht_id="test.always_bad",
            reason="bad_document",
            queue="dlq_name",
            failure_kind="permanent",
        )
        assert specific_error is not None
        assert specific_error["error_detail"] != ""


def test_bad_credentials_are_logged_as_config_error() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _error_response(401)
    service, _ = _make_service(solr_api_full_text)

    with capture_logs() as entries:
        service.process_batch(_batch(), [10, 11])

        assert_log_entry(
            entries,
            event="solr_request_failed",
            scope="batch",
            docs=2,
            failure_kind="config_error",
            failure_type="http_401",
        )


def test_counted_retries_log_the_attempt_and_exhaustion_is_the_dead_letter_reason() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _error_response(500)
    service, _ = _make_service(solr_api_full_text)
    service.max_retries = 1

    with capture_logs() as entries:
        for delivery_tag in (10, 11):
            service.process_batch([{"id": "test.retryable"}], [delivery_tag])

        assert_log_entry(
            entries,
            event="message_retried",
            ht_id="test.retryable",
            failure_kind="transient",
            attempt="1/1",
            error="",
        )

        assert_log_entry(
            entries,
            event="message_dead_lettered",
            ht_id="test.retryable",
            reason="retries_exhausted",
        )


def test_backoff_is_logged() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = requests.exceptions.ConnectionError("refused")
    service, _ = _make_service(solr_api_full_text)

    with capture_logs() as entries:
        service.process_batch(_batch(), [10, 11])

        assert_log_entry(
            entries,
            event="indexing_backoff",
            messages_put_back=2,
            consecutive_batches=1,
            wait_seconds=1.0,
        )


@pytest.mark.parametrize("status_code", [429, 502, 503, 504])
def test_unavailable_answers_keep_messages_on_the_queue_and_never_use_up_retries(
    status_code: int,
) -> None:
    """A proxy or Solr saying 'unavailable' during an outage must not dead-letter good messages."""
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _error_response(status_code)
    service, channel = _make_service(solr_api_full_text)
    service.max_retries = 2

    for delivery_tag in range(10, 20):
        service.process_batch([{"id": "1"}], [delivery_tag])

    assert len(_retried_tags(channel)) == 10
    assert channel.basic_reject.call_count == 0
    assert service.retry_attempts == {}
    # One request per batch: posting each document alone would get the same answer
    assert solr_api_full_text.index_documents.call_count == 10


def test_wrong_solr_url_or_missing_core_keeps_messages_on_the_queue() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _error_response(404)
    service, channel = _make_service(solr_api_full_text)

    with capture_logs() as entries:
        service.process_batch(_batch(), [10, 11])

        assert _retried_tags(channel) == [10, 11]
        assert channel.basic_reject.call_count == 0
        assert solr_api_full_text.index_documents.call_count == 1
        assert_log_entry(entries, failure_kind="config_error", failure_type="http_404")


def test_retries_are_keyed_by_the_document_id_not_by_the_whole_document() -> None:
    """Messages are Solr documents carrying the whole OCR text; it must not become a dict key."""
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _error_response(500)
    service, _ = _make_service(solr_api_full_text)
    document = {"id": "mdp.39015078560292", "ocr": "x" * 1_000_000}

    service.process_batch([document], [10])

    assert service.retry_attempts == {"mdp.39015078560292": 1}


def test_a_message_without_an_id_is_dead_lettered_once_and_never_retried() -> None:
    """Solr rejects a document without an id (400), so it goes to the DLQ for examination."""
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _error_response(400)
    service, channel = _make_service(solr_api_full_text)

    result = service.process_batch([{"title": "no id", "ocr": "x" * 1_000_000}], [10])

    assert result is False
    assert _dead_lettered_tags(channel) == [10]
    assert channel.basic_nack.call_count == 0
    assert service.retry_attempts == {}


def test_retry_log_shows_the_document_id_as_ht_id() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = _error_response(500)
    service, _ = _make_service(solr_api_full_text)

    with capture_logs() as entries:
        service.process_batch([{"id": "mdp.123", "ocr": "text"}], [10])

        assert_log_entry(entries, event="message_retried", ht_id="mdp.123")
