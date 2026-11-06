import contextlib
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
import sqlalchemy.exc
from document_generator.document_generator_service import DocumentGeneratorService
from document_generator.full_text_document_generator import FullTextDocumentGenerator
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

    def test_mysql_error_rejects_the_message_and_logs_the_ht_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End to end through the real FullTextDocumentGenerator and MysqlMetadataExtractor: a
        MySQL error must not produce a document with missing data. The message is rejected (not
        acked, not published) and the error is logged with the ht_id. Only the file-dependent
        steps (zip check, OCR text, full record) are stubbed."""
        monkeypatch.setenv("SDR_DIR", "/tmp/sdr1/obj")  # HtDocument reads it to find the zip
        db_conn = Mock()
        db_conn.query_mysql.side_effect = sqlalchemy.exc.SQLAlchemyError("mysql down")
        service = _make_service_with_mocks(db_conn)
        service.document_generator = FullTextDocumentGenerator(db_conn)
        message = {"ht_id": "mdp.39015078560292", "fullrecord": "<record/>"}

        with (
            patch("document_generator.document_generator_service.Path.is_file", return_value=True),
            patch.object(FullTextDocumentGenerator, "create_ocr_field", return_value={}),
            patch.object(FullTextDocumentGenerator, "create_allfields_field", return_value={}),
            patch.object(service, "publish_document") as publish,
            patch.object(service, "positive_acknowledge") as ack,
            patch.object(service, "reject_message") as reject,
            capture_logs() as entries,
        ):
            service.generate_document(message, delivery_tag=1)

        reject.assert_called_once()
        ack.assert_not_called()
        publish.assert_not_called()
        entry = find_log_entry(entries, event="document failed", ht_id="mdp.39015078560292")
        assert "mysql down" in str(entry["error"])
