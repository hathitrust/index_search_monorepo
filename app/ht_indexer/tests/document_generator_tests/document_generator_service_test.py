import contextlib
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from document_generator.document_generator_service import DocumentGeneratorService
from ht_utils.testing import capture_logs, find_log_entry


def _make_service_with_mocks(db_conn: Mock) -> DocumentGeneratorService:
    """DocumentGeneratorService.__init__ connects to a live RabbitMQ broker via its
    parent class (QueueMultipleConsumer), which isn't needed to exercise generate_document's
    own logic. Build the instance without running __init__ and set only what
    generate_document/log_error_document_generator_service actually touch -- mirrors the
    pattern in document_indexer_service_test.py's _make_service.
    """
    service = DocumentGeneratorService.__new__(DocumentGeneratorService)
    service.db_conn = db_conn
    service.document_repository = "pairtree"
    service.tgt_queue_producer = Mock()
    service.channel = MagicMock()
    service.requeue_message = False
    return service


VALID_MESSAGE: dict[str, Any] = {"ht_id": "mdp.39015078560292"}


class TestDocumentGeneratorService:
    def _make_service(self) -> tuple[DocumentGeneratorService, Mock]:
        db_conn = Mock()
        service = _make_service_with_mocks(db_conn)
        return service, db_conn

    @pytest.mark.parametrize(
        ("failing_method", "error", "expects_ack"),
        [
            pytest.param(None, None, True, id="success-acks-message"),
            pytest.param(
                "generate_full_text_entry",
                FileNotFoundError("zip not found"),
                False,
                id="failure-rejects-message",
            ),
        ],
    )
    def test_generate_document_ack_or_reject(
        self,
        failing_method: str | None,
        error: Exception | None,
        expects_ack: bool,
    ) -> None:
        service, _ = self._make_service()
        message = {"ht_id": "mdp.39015078560292"}
        with (
            patch.object(
                service,
                "generate_full_text_entry",
                return_value={"id": "mdp.39015078560292"},
            ),
            patch.object(service, "publish_document"),
            patch.object(service, failing_method, side_effect=error)
            if failing_method
            else contextlib.nullcontext(),
            patch.object(service, "positive_acknowledge") as ack,
            patch.object(service, "reject_message") as reject,
        ):
            service.generate_document(message, delivery_tag=1)

        if expects_ack:
            ack.assert_called_once()
            reject.assert_not_called()
        else:
            reject.assert_called_once()
            ack.assert_not_called()

    def test_generate_document_failure_logs_error_with_ht_id(self) -> None:
        service, _ = self._make_service()
        with (
            patch.object(
                service,
                "generate_full_text_entry",
                side_effect=FileNotFoundError("zip not found"),
            ),
            capture_logs() as entries,
        ):
            service.generate_document({"ht_id": "mdp.1"}, delivery_tag=1)

        entry = find_log_entry(entries, event="document failed", ht_id="mdp.1")
        assert "zip not found" in str(entry["error"])
