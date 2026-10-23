import argparse
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from conftest import (
    ConcreteQueueConsumer,
    close_channel_and_connection,
    create_test_queue_config,
    drain_ht_ids,
)
from document_retriever_service import run_retriever_service_by_file as by_file_module
from document_retriever_service.full_text_search_retriever_service import PublishCounts
from document_retriever_service.ht_status_retriever_service import get_non_processed_ids
from document_retriever_service.retriever_arguments import RetrieverServiceByFileArguments
from document_retriever_service.run_retriever_service_by_file import retrieve_documents_by_file
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

current_dir = Path(__file__).parent


@pytest.fixture()
def run(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> SimpleNamespace:
    """Run retrieve_documents_by_file on a messy file with the retriever service mocked.

    The file has 5 non-blank lines: 1 duplicate (mdp.1), 1 invalid ("bad id") and
    3 valid unique ids. The mocked service reports 1 published, 1 failed and 1 not in Catalog.

    :param tmp_path: pytest fixture for a temporary directory
    :param caplog: pytest fixture for capturing log records

    :return: SimpleNamespace with attributes:
        summary: ByFileSummary returned by retrieve_documents_by_file
        service: the mocked FullTextSearchRetrieverQueueService instance
        logs: list of log records captured during the run
    """

    input_file = tmp_path / "ids.txt"
    input_file.write_text(" mdp.1 \n\nmdp.2\nmdp.1\nbad id\nmdp.3\n")
    with patch.object(by_file_module, "FullTextSearchRetrieverQueueService") as service_cls:
        service = service_cls.return_value
        service.full_text_search_retriever_service.return_value = PublishCounts(
            published=1, failed=1, not_found=1
        )
        with caplog.at_level(logging.INFO):
            summary = retrieve_documents_by_file(
                MagicMock(),
                "item",
                "http://solr",
                "solr_user",
                "solr_password",
                {},
                input_file,
                tmp_path / "status.txt",
                False,
                MagicMock(),
                1,
            )
    return SimpleNamespace(summary=summary, service=service, logs=list(caplog.records))


@pytest.fixture
def make_args(
    stub_retriever_external_services: None,
) -> Callable[[list[str]], RetrieverServiceByFileArguments]:
    def _make(argv: list[str]) -> RetrieverServiceByFileArguments:
        return RetrieverServiceByFileArguments(argparse.ArgumentParser(), argv=argv)

    return _make


@pytest.fixture()
def get_input_file() -> Path:
    """TXT file containing the list of items to process"""
    file_path = current_dir.parent / "list_htids_indexer_test.txt"

    return file_path


@pytest.fixture()
def status_file(tmp_path: Path) -> str:
    """Creates and returns a temporary TXT file to store the status of items to process"""

    return str(tmp_path / "status.txt")


@pytest.fixture
def temp_input_file(tmp_path: Path) -> str:
    f = tmp_path / "htids.txt"
    f.write_text("")
    return str(f)


class TestRunRetrieverServiceByFile:
    def test_get_non_processed_ids(self, get_input_file: Path, status_file: str) -> None:
        with open(get_input_file) as f:
            list_ids = f.read().splitlines()

            ids2process, processed_ids = get_non_processed_ids(status_file, list_ids)
            assert len(ids2process) == 12
            assert len(processed_ids) == 0

    def test_run_retriever_service_by_file(
        self,
        get_input_file: Path,
        status_file: str,
        solr_catalog_url: str,
        get_retriever_service_solr_parameters: dict[str, Any],
        get_global_queue_config: dict[str, Any],
        get_app_queue_config: dict[str, Any],
    ) -> None:
        queue_name = "test_run_retriever_service_by_file"
        batch_size = 1
        requeue_message = False

        producer_queue_config, global_path, app_path = create_test_queue_config(
            get_global_queue_config,
            get_app_queue_config,
            queue_name,
            batch_size=batch_size,
            requeue_message=requeue_message,
        )

        mysql_db = MagicMock()  # Mock MySQL connection
        retrieve_documents_by_file(
            producer_queue_config.queue_params,
            "item",
            solr_catalog_url,
            "solr_user",
            "solr_password",
            get_retriever_service_solr_parameters,
            get_input_file,
            status_file,
            False,
            mysql_db,
            1,
        )

        consumer_instance = ConcreteQueueConsumer(producer_queue_config.queue_params)
        assert consumer_instance.channel is not None

        # Service to consume the messages
        ht_ids = drain_ht_ids(consumer_instance)

        assert all(
            item in ht_ids
            for item in [
                "nyp.33433082002258",
                "uiug.30112118465605",
                "mdp.39015086515536",
                "umn.31951001997704p",
                "wu.89039292644",
                "coo.31924093038853",
                "mdp.35112103801405",
                "mdp.35112103801975",
                "uiug.30112037580229",
            ]
        )

        # Clean up the queue, if the queue is already set up
        close_channel_and_connection(consumer_instance)

        # Delete the temporary files
        os.remove(global_path)
        os.remove(app_path)

    def test_retriever_by_file_arguments_status_file_default_not_in_src_package_dir(
        self,
        temp_input_file: str,
        stub_retriever_external_services: None,
        make_args: Callable[[list[str]], RetrieverServiceByFileArguments],
    ) -> None:
        # Arrange
        src_package_dir = str(Path(__file__).parents[2] / "src" / "document_retriever_service")

        args = make_args(["--input_document_file", temp_input_file])

        # Assert
        assert not args.status_file.startswith(src_package_dir)

    def test_retriever_by_file_arguments_status_file_overridable_via_cli(
        self,
        temp_input_file: str,
        stub_retriever_external_services: None,
        make_args: Callable[[list[str]], RetrieverServiceByFileArguments],
    ) -> None:
        # Act
        args = make_args(
            ["--input_document_file", temp_input_file, "--status_file", "/tmp/my_custom_status.txt"]
        )

        # Assert
        assert args.status_file == "/tmp/my_custom_status.txt"

    def test_get_non_processed_ids_missing_status_file_returns_all_unprocessed(self) -> None:
        # Arrange
        missing = os.path.join(tempfile.gettempdir(), "does_not_exist_status.txt")
        if os.path.exists(missing):
            os.remove(missing)
        list_ids = ["a", "b", "c"]

        # Act
        ids2process, processed_ids = get_non_processed_ids(missing, list_ids)

        # Assert
        assert processed_ids == []
        assert sorted(ids2process) == ["a", "b", "c"]


class TestReadIdsFromFile:
    @staticmethod
    def _read(tmp_path: Path, content: str, query_field: str = "item") -> Any:
        input_file = tmp_path / "ids.txt"
        input_file.write_text(content)
        return by_file_module.read_ids_from_file(input_file, query_field)

    @pytest.mark.parametrize(
        ("content", "field", "attr", "expected"),
        [
            pytest.param(
                "  mdp.1 \n\tmdp.2\r\n", "item", "ids", ["mdp.1", "mdp.2"], id="strips-whitespace"
            ),
            pytest.param("mdp.1\n\n   \nmdp.2\n", "item", "requested", 2, id="ignores-blank-lines"),
            pytest.param(
                "mdp.2\nmdp.1\n mdp.2\nmdp.1\n",
                "item",
                "ids",
                ["mdp.2", "mdp.1"],
                id="dedupes-keeps-order",
            ),
            pytest.param(
                "mdp.2\nmdp.1\n mdp.2\nmdp.1\n", "item", "duplicates", 2, id="counts-duplicates"
            ),
            pytest.param(
                "008394936\nmdp.1\n12345\n",
                "record",
                "invalid",
                ["mdp.1", "12345"],
                id="record-rejects-htid",
            ),
            pytest.param(
                "umn.31951001997704p\nuc2.ark:/13960/t0dv1g69b\n",
                "item",
                "invalid",
                [],
                id="real-htids-valid",
            ),
        ],
    )
    def test_read_ids_from_file(
        self, tmp_path: Path, content: str, field: str, attr: str, expected: object
    ) -> None:
        f = tmp_path / "ids.txt"
        f.write_text(content)
        assert getattr(by_file_module.read_ids_from_file(f, field), attr) == expected

    def test_read_ids_from_file_item_mode_malformed_ids_returned_as_invalid(
        self, tmp_path: Path
    ) -> None:
        content = "mdp.1\n008394936\nmdp 123\nmdp.1,mdp.2\nno_namespace\nMDP.1\n"

        ids_file = self._read(tmp_path, content, query_field="item")

        assert ids_file.invalid == ["008394936", "mdp 123", "mdp.1,mdp.2", "no_namespace", "MDP.1"]


class TestRetrieveDocumentsByFileSummary:
    @staticmethod
    def _messages(caplog: pytest.LogCaptureFixture, level: int | None = None) -> list[str]:
        """Return log messages at the given level, or all levels if level is None."""
        return [
            r.getMessage()
            for r in caplog.get_records("setup")
            if level is None or r.levelno == level
        ]

    def test_sends_only_valid_unique_ids(self, run: SimpleNamespace) -> None:
        _, sent_ids, _ = run.service.full_text_search_retriever_service.call_args.args
        assert sorted(sent_ids) == ["mdp.1", "mdp.2", "mdp.3"]

    def test_returns_summary(self, run: SimpleNamespace) -> None:
        assert run.summary == by_file_module.ByFileSummary(
            requested=5,
            duplicates=1,
            invalid=["bad id"],
            already_processed=0,
            seeded=1,
            errors=1,
            not_found=1,
        )

    def test_logs_summary_line(
        self, run: SimpleNamespace, caplog: pytest.LogCaptureFixture
    ) -> None:
        assert (
            "Retriever by file summary: requested=5 duplicates=1 invalid=1 "
            "already_processed=0 seeded=1 errors=1 not_found=1"
        ) in TestRetrieveDocumentsByFileSummary._messages(caplog, level=logging.INFO)

    def test_logs_error_for_invalid_id(
        self, run: SimpleNamespace, caplog: pytest.LogCaptureFixture
    ) -> None:
        errors = TestRetrieveDocumentsByFileSummary._messages(caplog, level=logging.ERROR)

        assert any("'bad id'" in message for message in errors)
