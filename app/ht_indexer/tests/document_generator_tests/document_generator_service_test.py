from typing import Any, cast
from unittest.mock import MagicMock, Mock, patch

from document_generator.document_generator_service import (
    FAILURE_UPDATE_STATUS,
    SUCCESS_UPDATE_STATUS,
    DocumentGeneratorService,
)


class TestDocumentGeneratorServiceMysqlUpdate:
    def _make_service(self) -> tuple[DocumentGeneratorService, Mock]:
        # Create a DocumentGeneratorService with a mocked MySQL connection and queue consumer/producer.
        db_conn = Mock()
        src_queue_consumer = Mock()
        src_queue_consumer.channel = MagicMock()
        tgt_queue_producer = Mock()
        service = DocumentGeneratorService(db_conn, src_queue_consumer, tgt_queue_producer)
        return service, db_conn

    def _generate_successfully(self) -> Mock:
        """Run generate_document down the success path and return the db_conn mock.

        generate_full_text_entry and publish_document are stubbed, so only generate_document's
        own ack/status-write logic runs. On success, MySQL must get status=processing and
        generator_status=completed.
        """
        service, db_conn = self._make_service()
        with (
            patch.object(
                service, "generate_full_text_entry", return_value={"id": "mdp.39015078560292"}
            ),
            patch.object(service, "publish_document"),
        ):
            service.generate_document({"ht_id": "mdp.39015078560292"}, delivery_tag=1)
        return db_conn

    def _generate_with_failure(self) -> Mock:
        """Run generate_document down the failure path and return the db_conn mock.

        On failure, MySQL must get status=failed and generator_status=failed, with an error.
        """
        service, db_conn = self._make_service()
        with patch.object(
            service, "generate_full_text_entry", side_effect=FileNotFoundError("zip not found")
        ):
            service.generate_document({"ht_id": "mdp.39015078560292"}, delivery_tag=1)
        return db_conn

    def test_generate_document_success_writes_status_once(self) -> None:
        db_conn = self._generate_successfully()

        db_conn.update_status.assert_called_once()

    def test_generate_document_success_uses_success_query(self) -> None:
        db_conn = self._generate_successfully()

        assert db_conn.update_status.call_args.args[0] == SUCCESS_UPDATE_STATUS

    def test_generate_document_success_sets_status_processing(self) -> None:
        db_conn = self._generate_successfully()

        assert db_conn.update_status.call_args.args[1][0]["status"] == "processing"

    def test_generate_document_success_sets_generator_status_completed(self) -> None:
        db_conn = self._generate_successfully()

        assert db_conn.update_status.call_args.args[1][0]["generator_status"] == "completed"

    def test_generate_document_success_writes_row_for_message_ht_id(self) -> None:
        db_conn = self._generate_successfully()

        assert db_conn.update_status.call_args.args[1][0]["ht_id"] == "mdp.39015078560292"

    def test_generate_document_failure_writes_status_once(self) -> None:
        db_conn = self._generate_with_failure()

        db_conn.update_status.assert_called_once()

    def test_generate_document_failure_uses_failure_query(self) -> None:
        db_conn = self._generate_with_failure()

        assert db_conn.update_status.call_args.args[0] == FAILURE_UPDATE_STATUS

    def test_generate_document_failure_sets_status_failed(self) -> None:
        db_conn = self._generate_with_failure()

        assert db_conn.update_status.call_args.args[1][0]["status"] == "failed"

    def test_generate_document_failure_sets_generator_status_failed(self) -> None:
        db_conn = self._generate_with_failure()

        assert db_conn.update_status.call_args.args[1][0]["generator_status"] == "failed"

    def test_generate_document_failure_writes_row_for_message_ht_id(self) -> None:
        db_conn = self._generate_with_failure()

        assert db_conn.update_status.call_args.args[1][0]["ht_id"] == "mdp.39015078560292"

    def test_generate_document_failure_records_non_empty_error(self) -> None:
        db_conn = self._generate_with_failure()

        assert db_conn.update_status.call_args.args[1][0]["error"]

    def test_generate_document_missing_ht_id_skips_update_status(self) -> None:
        service, db_conn = self._make_service()
        # Test the missing-ht_id guard returns before generate_full_text_entry runs.
        message: dict[str, Any] = {}

        service.generate_document(message, delivery_tag=1)

        db_conn.update_status.assert_not_called()

    def test_generate_document_success_update_placed_after_acknowledge(self) -> None:
        # Test that the status write runs after the message is acked, so a status-write error
        service, db_conn = self._make_service()
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
    def _make_service(self) -> tuple[DocumentGeneratorService, Mock]:
        # This make_service creates a DocumentGeneratorService with a mocked MySQL connection that raises
        db_conn = Mock()
        db_conn.update_status.side_effect = RuntimeError("MySQL unavailable")
        src_queue_consumer = Mock()
        src_queue_consumer.channel = MagicMock()
        service = DocumentGeneratorService(db_conn, src_queue_consumer, Mock())
        return service, db_conn

    def _generate_successfully(self, service: DocumentGeneratorService) -> None:
        with (
            patch.object(
                service, "generate_full_text_entry", return_value={"id": "mdp.39015078560292"}
            ),
            patch.object(service, "publish_document"),
        ):
            service.generate_document({"ht_id": "mdp.39015078560292"}, delivery_tag=1)

    def _generate_with_failure(self, service: DocumentGeneratorService) -> None:
        with patch.object(
            service, "generate_full_text_entry", side_effect=FileNotFoundError("zip not found")
        ):
            service.generate_document({"ht_id": "mdp.39015078560292"}, delivery_tag=1)

    def test_generate_document_success_status_write_error_does_not_reject_message(self) -> None:
        service, _ = self._make_service()

        self._generate_successfully(service)

        # Casting the callable to a MagicMock type
        cast(MagicMock, service.src_queue_consumer.reject_message).assert_not_called()

    def test_generate_document_success_status_write_error_does_not_write_failed_status(
        self,
    ) -> None:
        service, db_conn = self._make_service()

        self._generate_successfully(service)

        assert db_conn.update_status.call_args.args[0] == SUCCESS_UPDATE_STATUS

    def test_generate_document_failure_status_write_error_does_not_raise(self) -> None:
        service, db_conn = self._make_service()

        self._generate_with_failure(service)

        db_conn.update_status.assert_called_once()

    def test_generate_document_failure_status_write_error_still_rejects_message(self) -> None:
        service, _ = self._make_service()

        self._generate_with_failure(service)

        cast(MagicMock, service.src_queue_consumer.reject_message).assert_called_once()


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
