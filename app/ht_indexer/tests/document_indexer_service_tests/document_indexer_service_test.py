from typing import Any
from unittest.mock import MagicMock

from document_indexer_service.document_indexer_service import (
    FAILURE_UPDATE_STATUS,
    SUCCESS_UPDATE_STATUS,
    DocumentIndexerQueueService,
)


def _make_service(
    solr_api_full_text: MagicMock,
) -> tuple[DocumentIndexerQueueService, MagicMock, MagicMock]:
    """DocumentIndexerQueueService.__init__ connects to a live RabbitMQ broker via its
    parent class, which isn't needed to exercise process_batch's own logic. Build the
    instance without running __init__ and set only what process_batch actually touches.
    Returns the channel and db_conn mocks separately (typed as MagicMock, not
    BlockingChannel | None / HtMysql) so tests can assert on them without narrowing.
    """
    service = DocumentIndexerQueueService.__new__(DocumentIndexerQueueService)
    service.solr_api_full_text = solr_api_full_text
    channel = MagicMock()
    service.channel = channel
    service.queue_manager = MagicMock(dead_letter_queue_name="dlq_name")
    service.requeue_message = False
    db_conn = MagicMock()
    service.db_conn = db_conn
    return service, channel, db_conn


def _batch() -> list[dict[str, Any]]:
    return [{"ht_id": "1"}, {"ht_id": "2"}]


def test_process_batch_returns_true_and_acks_on_success() -> None:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = MagicMock(status_code=200)
    service, channel, _db_conn = _make_service(solr_api_full_text)
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
    service, channel, _db_conn = _make_service(solr_api_full_text)
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
    service, channel, _db_conn = _make_service(solr_api_full_text)
    batch = _batch()
    delivery_tags = [10, 11]

    result = service.process_batch(batch, delivery_tags)

    assert result is False
    assert channel.basic_reject.call_count == 2


class TestIndexerStatusSQLConstants:
    # These tests do not run queries or access MySQL. They pin the unconditional (CASE-free)
    # SQL used by the terminal-stage indexer.
    def test_success_update_status_sql_has_no_case_guard(self) -> None:
        assert "CASE" not in SUCCESS_UPDATE_STATUS

    def test_failure_update_status_sql_has_no_case_guard(self) -> None:
        assert "CASE" not in FAILURE_UPDATE_STATUS


def _ok_solr() -> MagicMock:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.return_value = MagicMock(status_code=200)
    return solr_api_full_text


def _failing_solr() -> MagicMock:
    solr_api_full_text = MagicMock()
    solr_api_full_text.index_documents.side_effect = RuntimeError("Solr down")
    return solr_api_full_text


def _status_rows(solr_api_full_text: MagicMock, batch: list[dict[str, Any]]) -> list[Any]:
    """Run process_batch and return the rows passed to the single update_status call."""
    service, _channel, db_conn = _make_service(solr_api_full_text)

    service.process_batch(batch, list(range(len(batch))))

    rows: list[Any] = db_conn.update_status.call_args.args[1]
    return rows


def _two_docs() -> list[dict[str, Any]]:
    return [{"id": "mdp.1"}, {"id": "mdp.2"}]


class TestIndexerStatusWrites:
    def test_process_batch_success_writes_status_once(self) -> None:
        service, _channel, db_conn = _make_service(_ok_solr())

        service.process_batch(_two_docs(), [1, 2])

        db_conn.update_status.assert_called_once()

    def test_process_batch_success_uses_success_query(self) -> None:
        service, _channel, db_conn = _make_service(_ok_solr())

        service.process_batch(_two_docs(), [1, 2])

        assert db_conn.update_status.call_args.args[0] == SUCCESS_UPDATE_STATUS

    def test_process_batch_success_writes_one_row_per_ht_id(self) -> None:
        rows = _status_rows(_ok_solr(), _two_docs())

        assert {row["ht_id"] for row in rows} == {"mdp.1", "mdp.2"}

    def test_process_batch_success_sets_indexer_status_completed(self) -> None:
        rows = _status_rows(_ok_solr(), _two_docs())

        assert [row["indexer_status"] for row in rows] == ["completed", "completed"]

    def test_process_batch_success_sets_status_completed(self) -> None:
        rows = _status_rows(_ok_solr(), _two_docs())

        assert [row["status"] for row in rows] == ["completed", "completed"]

    def test_process_batch_failure_writes_status_once(self) -> None:
        service, _channel, db_conn = _make_service(_failing_solr())

        service.process_batch(_two_docs(), [1, 2])

        db_conn.update_status.assert_called_once()

    def test_process_batch_failure_uses_failure_query(self) -> None:
        service, _channel, db_conn = _make_service(_failing_solr())

        service.process_batch(_two_docs(), [1, 2])

        assert db_conn.update_status.call_args.args[0] == FAILURE_UPDATE_STATUS

    def test_process_batch_failure_writes_one_row_per_ht_id(self) -> None:
        rows = _status_rows(_failing_solr(), _two_docs())

        assert {row["ht_id"] for row in rows} == {"mdp.1", "mdp.2"}

    def test_process_batch_failure_sets_indexer_status_failed(self) -> None:
        rows = _status_rows(_failing_solr(), _two_docs())

        assert [row["indexer_status"] for row in rows] == ["failed", "failed"]

    def test_process_batch_failure_sets_status_failed(self) -> None:
        rows = _status_rows(_failing_solr(), _two_docs())

        assert [row["status"] for row in rows] == ["failed", "failed"]

    def test_process_batch_failure_records_non_empty_error_for_every_row(self) -> None:
        rows = _status_rows(_failing_solr(), _two_docs())

        assert all(isinstance(row["error"], str) and row["error"] for row in rows)

    def test_process_batch_doc_without_id_is_excluded_from_status_write(self) -> None:
        rows = _status_rows(_ok_solr(), [{"id": "mdp.1"}, {"no_id": True}])

        assert [row["ht_id"] for row in rows] == ["mdp.1"]


class TestIndexerStatusWriteErrors:
    # A status write runs after messages are already acked or rejected, so its failure must not
    # reject an acked message or stop the consume loop.
    def test_process_batch_success_status_write_error_does_not_reject_acked_messages(
        self,
    ) -> None:
        service, channel, db_conn = _make_service(_ok_solr())
        db_conn.update_status.side_effect = RuntimeError("MySQL down")

        service.process_batch([{"id": "mdp.1"}], [1])

        channel.basic_reject.assert_not_called()

    def test_process_batch_success_status_write_error_does_not_raise_out_of_process_batch(
        self,
    ) -> None:
        service, _channel, db_conn = _make_service(_ok_solr())
        db_conn.update_status.side_effect = RuntimeError("MySQL down")

        result = service.process_batch([{"id": "mdp.1"}], [1])

        assert result is True

    def test_process_batch_failure_status_write_error_does_not_raise_out_of_process_batch(
        self,
    ) -> None:
        service, _channel, db_conn = _make_service(_failing_solr())
        db_conn.update_status.side_effect = RuntimeError("MySQL down")

        result = service.process_batch([{"id": "mdp.1"}], [1])

        assert result is False
