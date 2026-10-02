from typing import Any
from unittest.mock import ANY, MagicMock

import pytest
from conftest import IndexerServiceFactory
from document_indexer_service.document_indexer_service import (
    FAILURE_UPDATE_STATUS,
    SUCCESS_UPDATE_STATUS,
)


@pytest.fixture
def standard_batch() -> tuple[list[dict[str, Any]], list[int]]:
    """A fresh batch and matching delivery tags for evaluation."""
    return [{"id": "mdp.1"}, {"id": "mdp.2"}], [10, 11]


def test_process_batch_returns_true_and_acks_on_success(
    make_indexer_service: IndexerServiceFactory,
    standard_batch: tuple[list[dict[str, Any]], list[int]],
) -> None:
    batch, delivery_tags = standard_batch
    service, channel, _ = make_indexer_service()

    result = service.process_batch(batch, delivery_tags)

    assert result is True
    assert channel.basic_ack.call_count == 2
    assert batch == []
    assert delivery_tags == []


def test_process_batch_returns_false_when_batch_is_dead_lettered(
    make_indexer_service: IndexerServiceFactory,
    mock_solr: MagicMock,
    standard_batch: tuple[list[dict[str, Any]], list[int]],
) -> None:
    """Regression test: process_batch used to return True unconditionally, even when
    the whole batch failed and was dead-lettered, which meant callers had no way to
    tell success from failure. This fails against the old `return True` and passes
    now that process_batch reports the outcome honestly.
    """
    mock_solr.index_documents.side_effect = RuntimeError("Solr is unavailable")
    service, channel, _ = make_indexer_service(solr_api=mock_solr)
    batch, delivery_tags = standard_batch

    result = service.process_batch(batch, delivery_tags)

    assert result is False
    assert channel.basic_reject.call_count == 2
    assert batch == []
    assert delivery_tags == []


def test_process_batch_returns_false_when_solr_response_is_an_error_status(
    make_indexer_service: IndexerServiceFactory,
    mock_solr: MagicMock,
    standard_batch: tuple[list[dict[str, Any]], list[int]],
) -> None:
    response = MagicMock(status_code=500)
    response.raise_for_status.side_effect = RuntimeError("500 Server Error")
    mock_solr.index_documents.return_value = response
    service, channel, _ = make_indexer_service(solr_api=mock_solr)
    batch, delivery_tags = standard_batch

    result = service.process_batch(batch, delivery_tags)

    assert result is False
    assert channel.basic_reject.call_count == 2


class TestIndexerStatusWrites:
    """Pins recovery behaviors during database engine faults."""

    def test_process_batch_success_writes_all_rows_completely(
        self,
        make_indexer_service: IndexerServiceFactory,
        standard_batch: tuple[list[dict[str, Any]], list[int]],
    ) -> None:
        service, _, db_conn = make_indexer_service()
        batch, tags = standard_batch

        service.process_batch(batch, tags)

        # Asserts single call execution and structure cleanly [values]
        db_conn.update_status.assert_called_once_with(
            SUCCESS_UPDATE_STATUS,
            [
                {
                    "ht_id": "mdp.1",
                    "indexer_status": "completed",
                    "status": "completed",
                    "processed_at": ANY,
                },
                {
                    "ht_id": "mdp.2",
                    "indexer_status": "completed",
                    "status": "completed",
                    "processed_at": ANY,
                },
            ],
        )

    def test_process_batch_failure_writes_rows_with_error_traces(
        self,
        make_indexer_service: IndexerServiceFactory,
        mock_solr: MagicMock,
        standard_batch: tuple[list[dict[str, Any]], list[int]],
    ) -> None:
        mock_solr.index_documents.side_effect = RuntimeError("Solr down")
        service, _, db_conn = make_indexer_service(solr_api=mock_solr)
        batch, tags = standard_batch

        service.process_batch(batch, tags)

        db_conn.update_status.assert_called_once()
        query, rows = db_conn.update_status.call_args.args

        assert query == FAILURE_UPDATE_STATUS
        assert len(rows) == 2
        for row in rows:
            assert row["indexer_status"] == "failed"
            assert row["status"] == "failed"
            assert isinstance(row["error"], str) and "Solr down" in row["error"]

    def test_process_batch_excludes_documents_missing_identifier(
        self, make_indexer_service: IndexerServiceFactory
    ) -> None:
        service, _, db_conn = make_indexer_service()
        malformed_batch = [{"id": "mdp.1"}, {"no_id": ""}]

        service.process_batch(malformed_batch, [1, 2])

        _, rows = db_conn.update_status.call_args.args
        assert len(rows) == 1
        assert rows[0]["ht_id"] == "mdp.1"


class TestIndexerStatusWriteErrors:
    """A status write runs after messages are already acked or rejected, so its failure must not
    reject an acked message or stop the consume loop."""

    def test_success_status_write_error_swallows_exception_and_preserves_ack(
        self, make_indexer_service: IndexerServiceFactory
    ) -> None:
        service, channel, db_conn = make_indexer_service()
        db_conn.update_status.side_effect = RuntimeError("MySQL down")

        try:
            service.process_batch([{"id": "mdp.1"}], [1])
        except RuntimeError:
            pytest.fail("Service leaked a raw DB exception to consumer loops!")

        channel.basic_reject.assert_not_called()

    def test_simultaneous_solr_and_db_failure_still_safely_dead_letters_messages(
        self, make_indexer_service: IndexerServiceFactory, mock_solr: MagicMock
    ) -> None:
        """
        Worst-case scenario verification:
        When both Solr AND the Database crash at the same time, the worker loop
        must swallow the database exception and safely reject/dead-letter the
        messages so they are not permanently lost.
        """
        # 1. Arrange: Crash BOTH external dependencies simultaneously
        mock_solr.index_documents.side_effect = RuntimeError("Solr connection timed out")
        service, channel, db_conn = make_indexer_service(solr_api=mock_solr)
        db_conn.update_status.side_effect = RuntimeError(
            "MySQL instance is completely unresponsive"
        )

        batch = [{"id": "mdp.critical_doc"}]
        delivery_tags = [999]

        # 2. Act: Execute and explicitly assert that it doesn't raise a loop-crashing exception
        try:
            result = service.process_batch(batch, delivery_tags)
        except RuntimeError as e:
            pytest.fail(f"The worker loop crashed! An unhandled exception was leaked: {e}")

        # 3. Assert: The batch execution reports failure honestly
        assert result is False

        # 4. Assert: Even though the DB call failed, RabbitMQ dead-lettered the message safely
        channel.basic_reject.assert_called_once_with(
            delivery_tag=999,
            requeue=False,  # Requeue=False ensures RabbitMQ routes it straight to the DLQ ('dlq_name')
        )

        # 5. Assert: Verify the arrays were cleared to avoid stuck pointer mutations
        assert batch == []
        assert delivery_tags == []


class TestIndexerStatusSQL:
    # These tests do not run queries or access MySQL. They pin the shape of the indexer's SQL.

    def test_success_update_status_sql_clears_error(self) -> None:
        # An item that failed upstream and was later indexed must not keep the stale error.
        assert "error = NULL" in SUCCESS_UPDATE_STATUS
