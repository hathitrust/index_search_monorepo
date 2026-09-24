from typing import Any
from unittest.mock import MagicMock, Mock, patch

from document_generator.document_generator_service import (
    FAILURE_UPDATE_STATUS,
    SUCCESS_UPDATE_STATUS,
    DocumentGeneratorService,
)


class TestDocumentGeneratorServiceMysqlUpdate:
    def _make_service(self) -> tuple[DocumentGeneratorService, Mock]:
        db_conn = Mock()
        src_queue_consumer = Mock()
        src_queue_consumer.channel = MagicMock()
        tgt_queue_producer = Mock()
        service = DocumentGeneratorService(db_conn, src_queue_consumer, tgt_queue_producer)
        return service, db_conn

    def test_generate_document_success_calls_update_status_with_processing_and_completed(
        self,
    ) -> None:
        service, db_conn = self._make_service()
        message = {"ht_id": "mdp.39015078560292"}

        with patch.object(
            service, "generate_full_text_entry", return_value={"id": "mdp.39015078560292"}
        ):
            with patch.object(service, "publish_document"):
                service.generate_document(message, delivery_tag=1)

        db_conn.update_status.assert_called_once()
        query_arg, values_arg = db_conn.update_status.call_args.args
        assert query_arg == SUCCESS_UPDATE_STATUS
        update_dict = values_arg[0]
        assert update_dict["status"] == "processing"
        assert update_dict["generator_status"] == "completed"
        assert update_dict["ht_id"] == "mdp.39015078560292"

    def test_generate_document_failure_calls_update_status_with_failed_and_failed(
        self,
    ) -> None:
        service, db_conn = self._make_service()
        message = {"ht_id": "mdp.39015078560292"}

        with patch.object(
            service,
            "generate_full_text_entry",
            side_effect=FileNotFoundError("zip not found"),
        ):
            service.generate_document(message, delivery_tag=1)

        db_conn.update_status.assert_called_once()
        query_arg, values_arg = db_conn.update_status.call_args.args
        assert query_arg == FAILURE_UPDATE_STATUS
        update_dict = values_arg[0]
        assert update_dict["status"] == "failed"
        assert update_dict["generator_status"] == "failed"
        assert update_dict["ht_id"] == "mdp.39015078560292"
        assert "error" in update_dict
        assert update_dict["error"]

    def test_generate_document_missing_ht_id_skips_update_status(self) -> None:
        service, db_conn = self._make_service()
        # No patch needed: generate_document raises ValueError at the item_id is None
        # generate_full_text_entry is ever called.
        message: dict[str, Any] = {}

        service.generate_document(message, delivery_tag=1)

        db_conn.update_status.assert_not_called()

    def test_generate_document_success_update_placed_after_acknowledge(self) -> None:
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

        service.src_queue_consumer.reject_message.assert_not_called()  # type: ignore[attr-defined]  # Mock attribute

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

        service.src_queue_consumer.reject_message.assert_called_once()  # type: ignore[attr-defined]  # Mock attribute


class TestGeneratorStatusGuardInSQL:
    # These tests do not run queries or access MySQL. They pin the shape of the guard.
    # Only the shared status and error column is guarded, inside SET, so generator_status
    # is always written. status must be assigned last: MySQL evaluates SET left to right.
    def test_success_update_status_sql_guards_status_last_and_where_has_no_guard(self) -> None:
        assert SUCCESS_UPDATE_STATUS.endswith(
            "status = CASE WHEN status <> 'completed' THEN :status ELSE status END "
            "WHERE ht_id = :ht_id"
        )

    def test_failure_update_status_sql_guards_status_last_and_where_has_no_guard(self) -> None:
        assert FAILURE_UPDATE_STATUS.endswith(
            "status = CASE WHEN status <> 'completed' THEN :status ELSE status END "
            "WHERE ht_id = :ht_id"
        )

    def test_failure_update_status_sql_guards_error_when_row_is_completed(self) -> None:
        assert (
            "error = CASE WHEN status <> 'completed' THEN :error ELSE error END"
            in FAILURE_UPDATE_STATUS
        )
