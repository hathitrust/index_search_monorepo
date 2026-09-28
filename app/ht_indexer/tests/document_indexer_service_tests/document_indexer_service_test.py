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
from unittest.mock import MagicMock, Mock, patch

from document_indexer_service.document_indexer_service import (
    FAILURE_UPDATE_STATUS,
    SUCCESS_UPDATE_STATUS,
    DocumentIndexerQueueService,
)


class TestIndexerStatusSQLConstants:
    # These tests do not run queries or access MySQL. They pin the shape of the
    # unconditional (CASE-free) SQL used by the terminal-stage indexer.
    def test_success_update_status_sql_has_no_case_guard(self) -> None:
        assert "CASE" not in SUCCESS_UPDATE_STATUS

    def test_failure_update_status_sql_has_no_case_guard(self) -> None:
        assert "CASE" not in FAILURE_UPDATE_STATUS

    def test_success_update_status_sql_contains_indexer_status_column(self) -> None:
        assert "indexer_status" in SUCCESS_UPDATE_STATUS

    def test_failure_update_status_sql_contains_error_column(self) -> None:
        assert "error" in FAILURE_UPDATE_STATUS


def _make_service(
    solr_side_effect: Exception | None = None,
    solr_response: Mock | None = None,
) -> tuple[DocumentIndexerQueueService, Mock, Mock]:
    db_conn = Mock()
    solr_api = Mock()
    if solr_side_effect is not None:
        solr_api.index_documents = Mock(side_effect=solr_side_effect)
    else:
        solr_api.index_documents = Mock(return_value=solr_response)
    queue_params = Mock()
    with patch(
        "document_indexer_service.document_indexer_service.QueueMultipleConsumer.__init__",
        return_value=None,
    ):
        service = DocumentIndexerQueueService(solr_api, db_conn, queue_params)
    reject_mock = Mock()
    service.channel = MagicMock()
    service.queue_manager = MagicMock()

    # Using patch.object to override reject_messaje and positive_acknowledge, that are instance method, during a test without triggering Mypy errors
    # Use .start() to keep the mock active outside the helper fuction
    reject_mock = patch.object(service, 'reject_message', autospec=True).start()
    patch.object(service, 'positive_acknowledge', autospec=True).start()
    
    return service, db_conn, reject_mock


def _ok_response() -> Mock:
    response = Mock()
    response.status_code = 200
    response.raise_for_status = Mock()
    return response


class TestIndexerStatusWrites:
    def test_process_batch_success_writes_completed_for_every_ht_id_in_batch(self) -> None:
        service, db_conn, _ = _make_service(solr_response=_ok_response())
        batch: list[dict[str, Any]] = [{"id": "mdp.1"}, {"id": "mdp.2"}]

        service.process_batch(batch, [1, 2])

        db_conn.update_status.assert_called_once()
        query_arg, values_arg = db_conn.update_status.call_args.args
        assert query_arg == SUCCESS_UPDATE_STATUS
        assert len(values_arg) == 2
        assert all(v["indexer_status"] == "completed" for v in values_arg)
        assert all(v["status"] == "completed" for v in values_arg)
        assert {v["ht_id"] for v in values_arg} == {"mdp.1", "mdp.2"}

    def test_process_batch_failure_writes_failed_for_every_ht_id_in_batch(self) -> None:
        service, db_conn, _ = _make_service(solr_side_effect=Exception("Solr down"))
        batch: list[dict[str, Any]] = [{"id": "mdp.1"}, {"id": "mdp.2"}]

        service.process_batch(batch, [1, 2])

        db_conn.update_status.assert_called_once()
        query_arg, values_arg = db_conn.update_status.call_args.args
        assert query_arg == FAILURE_UPDATE_STATUS
        assert len(values_arg) == 2
        assert all(v["indexer_status"] == "failed" for v in values_arg)
        assert all(v["status"] == "failed" for v in values_arg)

    def test_process_batch_failure_writes_error_message_for_every_ht_id(self) -> None:
        service, db_conn, _ = _make_service(solr_side_effect=Exception("Solr down"))
        batch: list[dict[str, Any]] = [{"id": "mdp.1"}, {"id": "mdp.2"}]

        service.process_batch(batch, [1, 2])

        _query_arg, values_arg = db_conn.update_status.call_args.args
        for value in values_arg:
            assert "error" in value
            assert isinstance(value["error"], str)
            assert value["error"] != ""

    def test_process_batch_doc_without_id_is_excluded_from_status_write(self) -> None:
        service, db_conn, _ = _make_service(solr_response=_ok_response())
        batch: list[dict[str, Any]] = [{"id": "mdp.1"}, {"no_id": True}]

        service.process_batch(batch, [1, 2])

        db_conn.update_status.assert_called_once()
        _query_arg, values_arg = db_conn.update_status.call_args.args
        assert len(values_arg) == 1
        assert values_arg[0]["ht_id"] == "mdp.1"


class TestIndexerStatusWriteErrors:
    # A status write runs after messages are already acked or rejected, so its failure must not
    # reject an acked message or stop the consume loop.
    def test_process_batch_success_status_write_error_does_not_reject_acked_messages(
        self,
    ) -> None:
        service, db_conn, reject_mock = _make_service(solr_response=_ok_response())
        db_conn.update_status.side_effect = RuntimeError("MySQL down")
        batch: list[dict[str, Any]] = [{"id": "mdp.1"}]

        service.process_batch(batch, [1])

        reject_mock.assert_not_called()

    def test_process_batch_success_status_write_error_does_not_raise_out_of_process_batch(
        self,
    ) -> None:
        service, db_conn, _ = _make_service(solr_response=_ok_response())
        db_conn.update_status.side_effect = RuntimeError("MySQL down")
        batch: list[dict[str, Any]] = [{"id": "mdp.1"}]

        result = service.process_batch(batch, [1])

        assert result is True

    def test_process_batch_failure_status_write_error_does_not_raise_out_of_process_batch(
        self,
    ) -> None:
        service, db_conn, _ = _make_service(solr_side_effect=Exception("Solr down"))
        db_conn.update_status.side_effect = RuntimeError("MySQL down")
        batch: list[dict[str, Any]] = [{"id": "mdp.1"}]

        result = service.process_batch(batch, [1])

        assert result is True
