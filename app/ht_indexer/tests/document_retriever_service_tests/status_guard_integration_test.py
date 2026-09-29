from collections.abc import Generator
from typing import Any

import pytest
from catalog_metadata.ht_indexer_config import STATUS_COMPLETED, STATUS_PROCESSING
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

DELETE_TEST_ROW = f"DELETE FROM {PROCESSING_STATUS_TABLE_NAME} WHERE ht_id = :ht_id"


def _seed_row(status: str, generator_status: str, error: str | None) -> Generator[HtMysql]:
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
                "indexer_status": "pending",
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


def _fire_retriever_success_update(db_conn: HtMysql) -> dict[str, Any]:
    """Act: fire the retriever's SUCCESS update, then return the row as it stands afterward."""
    db_conn.update_status(
        SUCCESS_UPDATE_STATUS,
        [
            {
                "status": STATUS_PROCESSING,
                "retriever_status": STATUS_COMPLETED,
                "processed_at": get_current_time(),
                "ht_id": TEST_HT_ID,
            }
        ],
    )
    rows = db_conn.query_mysql(SELECT_ROW, {"ht_id": TEST_HT_ID})
    return rows[0]


@pytest.mark.integration
class TestStatusGuardIntegration:
    """A late retriever SUCCESS write must record retriever_status but must not overwrite
    the shared status (or the generator's columns) once the generator has written."""

    def test_retriever_success_on_non_pending_row_does_not_overwrite_status(
        self, seeded_failed_row: HtMysql
    ) -> None:
        row = _fire_retriever_success_update(seeded_failed_row)

        assert row["status"] == "failed"

    def test_retriever_success_on_non_pending_row_updates_retriever_status(
        self, seeded_failed_row: HtMysql
    ) -> None:
        row = _fire_retriever_success_update(seeded_failed_row)

        assert row["retriever_status"] == "completed"

    def test_retriever_success_on_non_pending_row_does_not_overwrite_generator_status(
        self, seeded_failed_row: HtMysql
    ) -> None:
        row = _fire_retriever_success_update(seeded_failed_row)

        assert row["generator_status"] == "failed"

    def test_retriever_success_on_non_pending_row_does_not_overwrite_error(
        self, seeded_failed_row: HtMysql
    ) -> None:
        row = _fire_retriever_success_update(seeded_failed_row)

        assert row["error"] == "test_error_from_generator"

    def test_retriever_success_on_pending_row_sets_status_processing(
        self, seeded_pending_row: HtMysql
    ) -> None:
        row = _fire_retriever_success_update(seeded_pending_row)

        assert row["status"] == "processing"
