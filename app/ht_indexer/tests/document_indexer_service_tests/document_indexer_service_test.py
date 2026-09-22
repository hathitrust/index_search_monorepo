from typing import Any
from unittest.mock import MagicMock

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


def test_process_batch_returns_true_and_acks_on_success() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = MagicMock(status_code=200)
    service, channel = _make_service(solr_api_full_text)
    batch = _batch()
    delivery_tags = [10, 11]

    result = service.process_batch(batch, delivery_tags)

    assert result is True
    assert channel.basic_ack.call_count == 2
    assert batch == []
    assert delivery_tags == []


def test_process_batch_returns_false_when_batch_is_dead_lettered() -> None:
    """Regression test: process_batch used to return True unconditionally, even when
    the whole batch failed and was dead-lettered, which meant callers had no way to
    tell success from failure. This fails against the old `return True` and passes
    now that process_batch reports the outcome honestly.
    """
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = RuntimeError("Solr is unavailable")
    service, channel = _make_service(solr_api_full_text)
    batch = _batch()
    delivery_tags = [10, 11]

    result = service.process_batch(batch, delivery_tags)

    assert result is False
    assert channel.basic_reject.call_count == 2
    assert batch == []
    assert delivery_tags == []


def test_process_batch_returns_false_when_solr_response_is_an_error_status() -> None:
    solr_api_full_text = MagicMock()
    response = MagicMock(status_code=500)
    response.raise_for_status.side_effect = RuntimeError("500 Server Error")
    solr_api_full_text.index_documents.return_value = response
    service, channel = _make_service(solr_api_full_text)
    batch = _batch()
    delivery_tags = [10, 11]

    result = service.process_batch(batch, delivery_tags)

    assert result is False
    assert channel.basic_reject.call_count == 2
