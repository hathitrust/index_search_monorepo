from typing import Any
from unittest.mock import MagicMock

import requests
from document_indexer_service.document_indexer_service import DocumentIndexerQueueService


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
    return service, channel


def _batch() -> list[dict[str, Any]]:
    return [{"ht_id": "1"}, {"ht_id": "2"}]


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
    batch: list[dict[str, Any]] = [{"ht_id": "1"}, {"ht_id": "2", "bad": True}, {"ht_id": "3"}]
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
    solr_api_full_text.index_documents.return_value = _error_response(503)
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
        _error_response(503),
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
    batch = [{"ht_id": "1"}, {"ht_id": "2"}, {"ht_id": "3"}]

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
