from collections.abc import Generator

import pytest
from catalog_metadata.ht_indexer_config import ProcessingStatus
from document_generator.document_generator_service import (
    SUCCESS_UPDATE_STATUS as GENERATOR_SUCCESS_UPDATE_STATUS,
)
from document_retriever_service.full_text_search_retriever_service import (
    SUCCESS_UPDATE_STATUS,
)
from ht_indexer_monitoring.ht_indexer_tracktable import (
    HT_INDEXER_TRACKTABLE,
    PROCESSING_STATUS_TABLE_NAME,
)
from ht_utils.ht_mysql import HtMysql, get_mysql_conn
from ht_utils.ht_utils import get_current_time

TEST_HT_ID = "test.guard_race_0001"
TEST_RECORD_ID = "test_record_guard_0001"

INSERT_TEST_ROW = f"""
    INSERT INTO {PROCESSING_STATUS_TABLE_NAME}
        (ht_id, record_id, status, retriever_status, generator_status, indexer_status, error)
    VALUES
        (:ht_id, :record_id, :status, :retriever_status, :generator_status, :indexer_status, :error)
    ON DUPLICATE KEY UPDATE
        status = VALUES(status),
        retriever_status = VALUES(retriever_status),
        generator_status = VALUES(generator_status),
        indexer_status = VALUES(indexer_status),
        error = VALUES(error)
"""

SELECT_ROW = f"""
    SELECT status, retriever_status, generator_status, error
    FROM {PROCESSING_STATUS_TABLE_NAME}
    WHERE ht_id = :ht_id
"""

SELECT_ROW_FULL = f"""
    SELECT status, retriever_status, generator_status, indexer_status, error
    FROM {PROCESSING_STATUS_TABLE_NAME}
    WHERE ht_id = :ht_id
"""

DELETE_TEST_ROW = f"DELETE FROM {PROCESSING_STATUS_TABLE_NAME} WHERE ht_id = :ht_id"


def _seed_row(
    status: str,
    generator_status: str,
    error: str | None,
    indexer_status: str = "pending",
) -> Generator[HtMysql]:
    """Insert the test row, yield the HtMysql connection, then delete the row.

    Uses update_status instead of query_mysql for insert and teardown: update_status
    runs inside engine.begin(), which commits on exit, while query_mysql uses
    engine.connect(), which does not commit the data into MySQL.
    """
    db_conn = get_mysql_conn(pool_size=1)
    db_conn.create_table(HT_INDEXER_TRACKTABLE)
    db_conn.update_status(
        INSERT_TEST_ROW,
        [
            {
                "ht_id": TEST_HT_ID,
                "record_id": TEST_RECORD_ID,
                "status": status,
                "retriever_status": "pending",
                "generator_status": generator_status,
                "indexer_status": indexer_status,
                "error": error,
            }
        ],
    )
    yield db_conn
    db_conn.update_status(DELETE_TEST_ROW, [{"ht_id": TEST_HT_ID}])


@pytest.fixture
def seeded_failed_row() -> Generator[HtMysql]:
    """Simulates the race: the generator ran and failed before the retriever's
    batched write landed (status='failed', generator_status='failed', error set)."""
    yield from _seed_row("failed", "failed", "test_error_from_generator")


@pytest.fixture
def seeded_pending_row() -> Generator[HtMysql]:
    """Normal flow: the retriever writes before the generator touches the row."""
    yield from _seed_row("pending", "pending", None)


@pytest.fixture
def seeded_indexer_completed_row() -> Generator[HtMysql]:
    """Simulates: the indexer completed the item (indexer_status='completed');
    the generator's ack write lands late."""
    yield from _seed_row("completed", "processing", None, indexer_status="completed")


@pytest.fixture
def seeded_indexer_failed_row() -> Generator[HtMysql]:
    """Simulates: the indexer failed (indexer_status='failed');
    a late generator success must not revert status."""
    yield from _seed_row("failed", "processing", "test_indexer_error", indexer_status="failed")


@pytest.mark.integration
class TestStatusGuardIntegration:
    """A late retriever SUCCESS write must record retriever_status but must not overwrite
    the shared status (or the generator's columns) once the generator has written."""

    def test_retriever_success_on_already_failed_row_only_updates_retriever_status(
        self, seeded_failed_row: HtMysql
    ) -> None:
        """A late retriever SUCCESS must write retriever_status but preserve existing errors/states."""
        db_conn = seeded_failed_row

        db_conn.update_status(
            SUCCESS_UPDATE_STATUS,
            [
                {
                    "status": ProcessingStatus.PROCESSING,
                    "retriever_status": ProcessingStatus.COMPLETED,
                    "processed_at": get_current_time(),
                    "ht_id": TEST_HT_ID,
                }
            ],
        )
        row = db_conn.query_mysql(SELECT_ROW_FULL, {"ht_id": TEST_HT_ID})[0]

        # Consolidated visual block: guarantees safety without 4 redundant SQL queries
        assert row == {
            "status": "failed",
            "retriever_status": "completed",
            "generator_status": "failed",
            "indexer_status": "pending",
            "error": "test_error_from_generator",
        }

    def test_retriever_success_on_clean_pending_row_progresses_pipeline_state(
        self, seeded_pending_row: HtMysql
    ) -> None:
        db_conn = seeded_pending_row

        db_conn.update_status(
            SUCCESS_UPDATE_STATUS,
            [
                {
                    "status": ProcessingStatus.PROCESSING,
                    "retriever_status": ProcessingStatus.COMPLETED,
                    "processed_at": get_current_time(),
                    "ht_id": TEST_HT_ID,
                }
            ],
        )
        row = db_conn.query_mysql(SELECT_ROW_FULL, {"ht_id": TEST_HT_ID})[0]

        assert row["status"] == "processing"
        assert row["retriever_status"] == "completed"

    def test_retriever_success_with_unknown_ht_id_silently_ignores_update(
        self, seeded_pending_row: HtMysql
    ) -> None:
        """
        Verifies that passing a non-existent ht_id doesn't throw a database exception,
        and leaves existing data records completely untouched.
        """
        db_conn = seeded_pending_row
        unknown_ht_id = "test.completely_non_existent_id_9999"

        # Execute an update using an ID that has never been seeded
        try:
            db_conn.update_status(
                SUCCESS_UPDATE_STATUS,
                [
                    {
                        "status": ProcessingStatus.PROCESSING,
                        "retriever_status": ProcessingStatus.COMPLETED,
                        "processed_at": get_current_time(),
                        "ht_id": unknown_ht_id,
                    }
                ],
            )
        except Exception as e:
            pytest.fail(f"Database tracking threw an unexpected error on a missing record: {e}")

        # Verify the missing ID was not accidentally inserted/created
        missing_row = db_conn.query_mysql(SELECT_ROW_FULL, {"ht_id": unknown_ht_id})
        assert len(missing_row) == 0, (
            f"Expected zero rows, but found an unexpected orphan record: {missing_row}"
        )

        # Verify our seeded control record was left completely untouched
        control_row = db_conn.query_mysql(SELECT_ROW_FULL, {"ht_id": TEST_HT_ID})
        assert control_row[0] == {
            "status": "pending",
            "retriever_status": "pending",
            "generator_status": "pending",
            "indexer_status": "pending",
            "error": None,
        }


@pytest.mark.integration
class TestTerminalStateGuardIntegration:
    """Terminal states written by the indexer must not be overwritten by upstream stages."""

    def test_late_generator_success_on_completed_indexer_row_retains_terminal_state(
        self, seeded_indexer_completed_row: HtMysql
    ) -> None:
        db_conn = seeded_indexer_completed_row

        db_conn.update_status(
            GENERATOR_SUCCESS_UPDATE_STATUS,
            [
                {
                    "status": ProcessingStatus.PROCESSING,
                    "generator_status": ProcessingStatus.COMPLETED,
                    "processed_at": get_current_time(),
                    "ht_id": TEST_HT_ID,
                }
            ],
        )
        row = db_conn.query_mysql(SELECT_ROW_FULL, {"ht_id": TEST_HT_ID})[0]

        assert row["status"] == "completed"
        assert row["generator_status"] == "completed"
        assert row["indexer_status"] == "completed"

    def test_late_generator_success_on_failed_indexer_row_does_not_mask_error(
        self, seeded_indexer_failed_row: HtMysql
    ) -> None:
        db_conn = seeded_indexer_failed_row

        db_conn.update_status(
            GENERATOR_SUCCESS_UPDATE_STATUS,
            [
                {
                    "status": ProcessingStatus.PROCESSING,
                    "generator_status": ProcessingStatus.COMPLETED,
                    "processed_at": get_current_time(),
                    "ht_id": TEST_HT_ID,
                }
            ],
        )
        row = db_conn.query_mysql(SELECT_ROW_FULL, {"ht_id": TEST_HT_ID})[0]

        assert row["status"] == "failed"
        assert row["generator_status"] == "completed"
        assert row["error"] == "test_indexer_error"
