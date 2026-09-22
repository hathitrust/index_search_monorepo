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

        original_positive_acknowledge = service.src_queue_consumer.positive_acknowledge

        def record_ack(*args, **kwargs): 
            call_order.append("ack")
            return original_positive_acknowledge(*args, **kwargs)

        def record_update_status(*args, **kwargs): 
            call_order.append("update_status")

        # src_queue_consumer is a Mock at runtime (not a real QueueConsumer)
        service.src_queue_consumer.positive_acknowledge = record_ack 
        db_conn.update_status.side_effect = record_update_status

        with patch.object(
            service, "generate_full_text_entry", return_value={"id": "mdp.39015078560292"}
        ):
            with patch.object(service, "publish_document"):
                service.generate_document(message, delivery_tag=1)

        assert call_order == ["ack", "update_status"], (
            f"Expected ack before update_status, got order: {call_order}"
        )
