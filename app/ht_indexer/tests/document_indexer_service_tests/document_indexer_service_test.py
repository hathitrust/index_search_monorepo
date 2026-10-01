from typing import Any
from unittest.mock import MagicMock

import pytest
import structlog
from document_indexer_service.document_indexer_service import DocumentIndexerQueueService
from ht_utils.ht_logger import get_ht_logger
from structlog.testing import LogCapture


@pytest.fixture
def caplog() -> LogCapture:
    return LogCapture()


@pytest.fixture(autouse=True)
def fixture_configure_structlog(caplog: LogCapture) -> None:
    print("CONFIGURING LOG CAPTURE")
    structlog.configure(processors=[caplog])


def _make_service(solr_api_full_text: MagicMock) -> tuple[DocumentIndexerQueueService, MagicMock]:
    """DocumentIndexerQueueService.__init__ connects to a live RabbitMQ broker via its
    parent class, which isn't needed to exercise process_batch's own logic. Build the
    instance without running __init__ and set only what process_batch actually touches.
    Returns the channel mock separately (typed as MagicMock, not BlockingChannel | None)
    so tests can assert on it without a None-narrowing check.
    """
    # FIXME look at using composition instead of inheritance - inject a fake
    # QueueMultipleConsumer
    service = DocumentIndexerQueueService.__new__(DocumentIndexerQueueService)
    service.solr_api_full_text = solr_api_full_text
    channel = MagicMock()
    service.channel = channel
    service.queue_manager = MagicMock(dead_letter_queue_name="dlq_name")
    service.requeue_message = False
    service.logger = get_ht_logger(__file__)
    return service, channel


# list of solr documents
def _batch() -> list[dict[str, Any]]:
    return [{"id": "test.item1"}, {"id": "test.item2"}]


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


def test_process_batch_logs_document_ids(caplog: LogCapture) -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = MagicMock(status_code=200)
    service, channel = _make_service(solr_api_full_text)
    batch = _batch()

    service.process_batch(batch, [])

    assert any(log.get("ht_id") == "test.item1" for log in caplog.entries)
    assert any(log.get("ht_id") == "test.item2" for log in caplog.entries)


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
