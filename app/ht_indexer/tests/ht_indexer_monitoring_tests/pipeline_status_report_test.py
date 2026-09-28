from typing import Any
from unittest.mock import Mock

import pytest
from ht_indexer_monitoring.pipeline_status_report import build_status_counts, print_status_report


class TestPipelineStatusReport:
    def _mock_db(self, rows: list[dict[str, Any]]) -> Mock:
        db = Mock()
        db.query_mysql.return_value = rows
        return db

    def test_build_query_result_groups_and_counts_correctly(self) -> None:
        rows = [
            {
                "retriever_status": "completed",
                "generator_status": "completed",
                "indexer_status": "completed",
                "status": "completed",
                "cnt": 5,
            },
            {
                "retriever_status": "completed",
                "generator_status": "failed",
                "indexer_status": "pending",
                "status": "failed",
                "cnt": 2,
            },
        ]
        db = self._mock_db(rows)

        counts = build_status_counts(db, ["test.1", "test.2"], chunk_size=500)

        assert sum(counts.values()) == 7
        key = ("completed", "completed", "completed", "completed")
        assert counts[key] == 5

    def test_report_prints_total_line_to_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        rows = [
            {
                "retriever_status": "completed",
                "generator_status": "completed",
                "indexer_status": "completed",
                "status": "completed",
                "cnt": 3,
            }
        ]
        db = self._mock_db(rows)

        print_status_report(db, ["test.1"], chunk_size=500)

        captured = capsys.readouterr()
        assert "Total:" in captured.out

    def test_empty_ht_id_list_prints_zero_total(self, capsys: pytest.CaptureFixture[str]) -> None:
        db = Mock()

        print_status_report(db, [], chunk_size=500)

        captured = capsys.readouterr()
        assert "Total: 0" in captured.out
