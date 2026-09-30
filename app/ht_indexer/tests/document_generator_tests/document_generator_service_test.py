from typing import Any, cast
from unittest.mock import ANY, MagicMock, Mock, patch

import pytest
from document_generator.document_generator_service import (
    FAILURE_UPDATE_STATUS,
    SUCCESS_UPDATE_STATUS,
    DocumentGeneratorService,
)


class TestDocumentGeneratorServiceMysqlUpdate:
    def test_generate_document_success_updates_database_correctly(
        self, make_generator_service: tuple[DocumentGeneratorService, Mock]
    ) -> None:
        service, db_conn = make_generator_service
        message = {"ht_id": "mdp.39015078560292"}

        with (
            patch.object(
                service, "generate_full_text_entry", return_value={"id": message["ht_id"]}
            ),
            patch.object(service, "publish_document"),
        ):
            service.generate_document(message, delivery_tag=1)

        # Assert all success database parameters
        db_conn.update_status.assert_called_once_with(
            SUCCESS_UPDATE_STATUS,
            [
                {
                    "status": "processing",
                    "generator_status": "completed",
                    "processed_at": ANY,
                    "ht_id": message["ht_id"],
                }
            ],
        )

    def test_generate_document_failure_updates_database_with_error(
        self, make_generator_service: tuple[DocumentGeneratorService, Mock]
    ) -> None:
        service, db_conn = make_generator_service
        message = {"ht_id": "mdp.39015078560292"}

        with patch.object(
            service, "generate_full_text_entry", side_effect=FileNotFoundError("zip not found")
        ):
            service.generate_document(message, delivery_tag=1)

        # Assert all failure parameters cleanly
        db_conn.update_status.assert_called_once()
        query, params_list = db_conn.update_status.call_args.args

        # Target the dictionary inside the list wrapper [values]
        actual_payload = params_list[0]

        assert query == FAILURE_UPDATE_STATUS
        assert actual_payload["status"] == "failed"
        assert actual_payload["generator_status"] == "failed"
        assert actual_payload["ht_id"] == message["ht_id"]
        assert "zip not found" in actual_payload["error"]

    def test_generate_document_missing_ht_id_skips_update_status(
        self, make_generator_service: tuple[DocumentGeneratorService, Mock]
    ) -> None:
        service, db_conn = make_generator_service
        # Test the missing-ht_id guard returns before generate_full_text_entry runs.
        message: dict[str, Any] = {}

        service.generate_document(message, delivery_tag=1)

        db_conn.update_status.assert_not_called()

    def test_generate_document_success_update_placed_after_acknowledge(
        self, make_generator_service: tuple[DocumentGeneratorService, Mock]
    ) -> None:
        # Test that the status write runs after the message is acked, so a status-write error
        service, db_conn = make_generator_service
        message = {"ht_id": "mdp.39015078560292"}
        call_order: list[str] = []

        def record_ack(*args: object, **kwargs: object) -> None:
            call_order.append("ack")

        def record_update_status(*args: object, **kwargs: object) -> None:
            call_order.append("update_status")

        db_conn.update_status.side_effect = record_update_status

        with (
            patch.object(
                service.src_queue_consumer, "positive_acknowledge", side_effect=record_ack
            ),
            patch.object(
                service, "generate_full_text_entry", return_value={"id": "mdp.39015078560292"}
            ),
            patch.object(service, "publish_document"),
        ):
            service.generate_document(message, delivery_tag=1)

        assert call_order == ["ack", "update_status"], (
            f"Expected ack before update_status, got order: {call_order}"
        )


class TestGeneratorStatusWriteErrors:
    # A status write runs after the message is already acked or rejected, so its failure must not
    # reject an acked message, record a published document as failed, or stop the consume loop.

    @pytest.fixture
    def setup_broken_db_service(self) -> tuple[DocumentGeneratorService, Mock]:
        """Fixture providing a DocumentGeneratorService with a mocked MySQL connection that raises RuntimeError"""
        db_conn = Mock()
        db_conn.update_status.side_effect = RuntimeError("MySQL unavailable")

        src_queue_consumer = Mock()
        src_queue_consumer.channel = MagicMock()

        service = DocumentGeneratorService(db_conn, src_queue_consumer, Mock())
        return service, db_conn

    def test_status_write_error_on_successful_generation_swallows_exception_and_keeps_ack(
        self, setup_broken_db_service: tuple[DocumentGeneratorService, Mock]
    ) -> None:
        """A DB error during success status update shouldn't crash the loop or reject the message."""
        service, _ = setup_broken_db_service
        message = {"ht_id": "mdp.39015078560292"}

        with (
            patch.object(
                service, "generate_full_text_entry", return_value={"id": message["ht_id"]}
            ),
            patch.object(service, "publish_document"),
        ):
            # Verify it swallows the RuntimeError and doesn't crash
            try:
                service.generate_document(message, delivery_tag=1)
            except RuntimeError:
                pytest.fail("Service leaked a database RuntimeError on the success path!")

        # Assert consumer behavior remains un-rejected
        reject_mock = cast(MagicMock, service.src_queue_consumer.reject_message)
        reject_mock.assert_not_called()

    def test_status_write_error_on_failed_generation_swallows_exception_and_still_rejects(
        self, setup_broken_db_service: tuple[DocumentGeneratorService, Mock]
    ) -> None:
        """A DB error during failure status update shouldn't mask the underlying code failure or skip rejections."""
        service, db_conn = setup_broken_db_service
        message = {"ht_id": "mdp.39015078560292"}

        with patch.object(
            service, "generate_full_text_entry", side_effect=FileNotFoundError("zip not found")
        ):
            # Act & Assert: Verify it swallows the DB error instead of crashing the worker loop
            try:
                service.generate_document(message, delivery_tag=1)
            except RuntimeError:
                pytest.fail("Service leaked a database RuntimeError on the failure path!")

        # Verify it still attempted to write to the DB and successfully rejected the message
        db_conn.update_status.assert_called_once()

        reject_mock = cast(MagicMock, service.src_queue_consumer.reject_message)
        reject_mock.assert_called_once_with(service.src_queue_consumer.channel, 1)


class TestGeneratorStatusGuardInSQL:
    # These tests do not run queries or access MySQL. They pin the shape of the guard.
    # Only the shared status and error column is guarded, inside SET, so generator_status
    # is always written. status must be assigned last: MySQL evaluates SET left to right.
    def test_success_update_status_sql_guards_status_last_and_where_has_no_guard(self) -> None:
        assert SUCCESS_UPDATE_STATUS.endswith(
            "status = CASE WHEN status NOT IN ('completed', 'failed') THEN :status ELSE status END "
            "WHERE ht_id = :ht_id"
        )

    def test_failure_update_status_sql_guards_status_last_and_where_has_no_guard(self) -> None:
        assert FAILURE_UPDATE_STATUS.endswith(
            "status = CASE WHEN status NOT IN ('completed', 'failed') THEN :status ELSE status END "
            "WHERE ht_id = :ht_id"
        )

    def test_failure_update_status_sql_guards_error_when_row_is_not_terminal(self) -> None:
        assert (
            "error = CASE WHEN status NOT IN ('completed', 'failed') THEN :error ELSE error END"
            in FAILURE_UPDATE_STATUS
        )
