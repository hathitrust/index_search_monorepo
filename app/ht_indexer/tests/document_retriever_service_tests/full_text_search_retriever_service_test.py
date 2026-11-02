import argparse
import contextlib
import json
import os
import sys
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from catalog_metadata.catalog_metadata import CatalogItemMetadata, CatalogRecordMetadata
from conftest import (
    ConcreteQueueConsumer,
    close_channel_and_connection,
    create_test_queue_config,
    drain_ht_ids,
    ensure_queue_ready_and_purged,
)
from document_retriever_service import (
    full_text_search_retriever_service as retriever_service_module,
)
from document_retriever_service.full_text_search_retriever_service import (
    ChunkMetadata,
    FullTextSearchRetrieverQueueService,
    PublishCounts,
)
from document_retriever_service.retriever_arguments import RetrieverServiceArguments
from document_retriever_service.retriever_services_utils import RetrieverServicesUtils
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_utils.ht_logger import get_ht_logger
from ht_utils.query_maker import make_solr_term_query
from ht_utils.testing import assert_log_entry, capture_logs

logger = get_ht_logger(name=__name__)

RECORD_ID = "008394936"
RECORD_HT_IDS = [
    "nyp.33433082002258",
    "nyp.33433082046495",
    "nyp.33433082046503",
    "nyp.33433082046529",
    "nyp.33433082046537",
]
FAKE_CATALOG_URL = "http://solr-sdr-catalog:9033/solr/catalogFake"


def _solr_output_one_record_five_items() -> dict[str, Any]:
    """Solr response with one record holding more items than any test requests."""
    return {
        "response": {
            "docs": [
                {
                    "id": RECORD_ID,
                    "ht_id": list(RECORD_HT_IDS),
                    "htsource": ["New York Public Library"] * len(RECORD_HT_IDS),
                }
            ]
        }
    }


def _items_for(
    service: FullTextSearchRetrieverQueueService, ids: list[str], by_field: str, sorl: HTSolrAPI
) -> list[CatalogItemMetadata]:

    # Build the query to retrieve the total of documents to process
    query = make_solr_term_query(ids, by_field)

    # Retrieve the documents from Solr
    output = json.loads(service.retrieve_documents_from_solr(query, sorl).content.decode("utf-8"))

    # Generate the metadata for the documents
    return FullTextSearchRetrieverQueueService.generate_chunk_metadata(ids, output, by_field).items


def _fail_metadata_of(fail_on: str) -> contextlib.AbstractContextManager[Any]:
    """Force a metadata error: for the whole record, or for RECORD_HT_IDS[1] only."""
    if fail_on == "record":
        return patch.object(
            retriever_service_module,
            "CatalogRecordMetadata",
            side_effect=ValueError("bad record"),
        )
    real_get_catalog_object = RetrieverServicesUtils.get_catalog_object

    def _get_catalog_object(
        item_id: str, record_metadata: CatalogRecordMetadata
    ) -> CatalogItemMetadata:
        if item_id == RECORD_HT_IDS[1]:
            raise ValueError("bad item")
        return real_get_catalog_object(item_id, record_metadata)

    return patch.object(
        RetrieverServicesUtils, "get_catalog_object", side_effect=_get_catalog_object
    )


@pytest.fixture
def queue_config(
    get_global_queue_config: dict[str, Any], get_app_queue_config: dict[str, Any]
) -> tuple[Any, Any, Any]:
    """This function is used to create the queue configuration

    :param get_global_queue_config: fixture to get the global queue configuration
    :param get_app_queue_config: fixture to get the application queue configuration
    : return: tuple containing the queue configuration object, global config path, and app config path

    """

    queue_name = "test_full_text_search_retriever_service"
    batch_size = 1
    requeue_message = False
    producer_queue_config, global_path, app_path = create_test_queue_config(
        get_global_queue_config,
        get_app_queue_config,
        queue_name,
        batch_size=batch_size,
        requeue_message=requeue_message,
    )

    return producer_queue_config, global_path, app_path


@pytest.fixture
def get_catalog_retriever_service_solr_fake_solr_url() -> HTSolrAPI:
    return HTSolrAPI(FAKE_CATALOG_URL, "solr_user", "solr_password")


@pytest.fixture
def solr_client(solr_catalog_url: str) -> HTSolrAPI:
    return HTSolrAPI(solr_catalog_url, "solr_user", "solr_password")


@pytest.fixture
def get_document_retriever_service(
    solr_catalog_url: str,
    get_retriever_service_solr_parameters: dict[str, Any],
    queue_config: tuple[Any, Any, Any],
) -> FullTextSearchRetrieverQueueService:
    """Fixture to create the document retriever service object
    :param solr_catalog_url: fixture to get the Solr URL
    :param get_retriever_service_solr_parameters: fixture to get the Solr parameters
    :param queue_config: fixture to get the queue configuration
    : return: FullTextSearchRetrieverQueueService object
    """
    return FullTextSearchRetrieverQueueService(
        queue_config[0].queue_params,
        solr_catalog_url,
        "solr_user",
        "solr_password",
        get_retriever_service_solr_parameters,
    )


class TestFullTextRetrieverService:
    def test_full_text_retriever_service_query(self) -> None:
        """Use case: Check if the Solr query is created correctly"""
        list_documents = ["nyp.33433082002258", "not_exist_document"]
        query = make_solr_term_query(list_documents, by_field="item")
        assert query == """{!terms f=ht_id separator=\" \"}nyp.33433082002258 not_exist_document"""

    @pytest.mark.integration
    def test_full_text_service_retrieve_documents_from_solr(
        self,
        get_document_retriever_service: FullTextSearchRetrieverQueueService,
        solr_client: HTSolrAPI,
    ) -> None:
        """Use case: Check if the documents are retrieved from Solr"""
        list_documents = ["nyp.33433082002258", "not_exist_document"]

        query = make_solr_term_query(list_documents, by_field="item")

        response = get_document_retriever_service.retrieve_documents_from_solr(query, solr_client)

        output = json.loads(response.content.decode("utf-8"))
        assert output.get("response").get("numFound") == 1

    def test_generate_metadata(self, get_item_metadata: CatalogItemMetadata) -> None:
        """Use case: Generate the metadata of the item to be indexed"""
        list_documents = ["mdp.39015078560292"]

        metadata, item_id = FullTextSearchRetrieverQueueService.generate_metadata(get_item_metadata)

        assert metadata.get("ht_id") == list_documents[0]
        assert metadata.get("countryOfPubStr") == ["India"]
        assert item_id == list_documents[0]

    @pytest.mark.parametrize("by_field", ["item", "ht_id"])
    def test_generate_chunk_metadata_non_record_field_returns_only_requested_items(
        self, by_field: str
    ) -> None:
        """Use case: the query was by ht_id, so only the requested items of the record are returned.

        "ht_id" covers the regression where any by_field other than "item" fell into the record
        branch and published every item of the record (1000 requested -> ~17000 published).
        """
        requested_documents = ["nyp.33433082002258", "nyp.33433082046495"]

        chunk_metadata = FullTextSearchRetrieverQueueService.generate_chunk_metadata(
            requested_documents, _solr_output_one_record_five_items(), by_field
        )

        assert sorted(item.ht_id for item in chunk_metadata.items) == sorted(requested_documents)

    def test_generate_chunk_metadata_catalog_record_builds_requested_item_metadata(
        self, get_record_data: dict[str, Any]
    ) -> None:
        """Use case: a real Catalog record builds the metadata of the requested item only."""
        chunk_metadata = FullTextSearchRetrieverQueueService.generate_chunk_metadata(
            ["mdp.39015078560292"], {"response": {"docs": [get_record_data]}}, "item"
        )

        assert [item.metadata.get("vol_id") for item in chunk_metadata.items] == [
            "mdp.39015078560292"
        ]

    def test_generate_chunk_metadata_by_record_returns_all_items(self) -> None:
        """Use case: the query was by record id, so every item of the record is returned."""
        requested_documents = [RECORD_ID]

        chunk_metadata = FullTextSearchRetrieverQueueService.generate_chunk_metadata(
            requested_documents, _solr_output_one_record_five_items(), "record"
        )

        assert sorted(item.ht_id for item in chunk_metadata.items) == sorted(RECORD_HT_IDS)

    @pytest.mark.parametrize(
        ("by_field", "requested", "fail_on", "expected"),
        [
            pytest.param(
                "item",
                RECORD_HT_IDS[:2],
                "item",
                ([RECORD_HT_IDS[0]], [RECORD_HT_IDS[1]]),
                id="bad-item-fails-only-itself",
            ),
            pytest.param(
                "item",
                RECORD_HT_IDS[:2],
                "record",
                ([], RECORD_HT_IDS[:2]),
                id="bad-record-fails-its-requested-ht-ids",
            ),
            pytest.param(
                "record",
                [RECORD_ID],
                "record",
                ([], RECORD_HT_IDS),
                id="bad-record-in-record-mode-fails-all-its-items",
            ),
        ],
    )
    def test_generate_chunk_metadata_metadata_error_reports_failed_ht_ids(
        self,
        by_field: str,
        requested: list[str],
        fail_on: str,
        expected: tuple[list[str], list[str]],
    ) -> None:
        """Use case: a metadata error drops only the affected ht_ids, and reports them as failed."""
        with _fail_metadata_of(fail_on):
            chunk_metadata = FullTextSearchRetrieverQueueService.generate_chunk_metadata(
                requested, _solr_output_one_record_five_items(), by_field
            )

        assert (
            sorted(item.ht_id for item in chunk_metadata.items),
            sorted(chunk_metadata.failed),
        ) == expected

    def test_retriever_arguments_catalog_credentials_set_used_for_solr(
        self,
        monkeypatch: pytest.MonkeyPatch,
        stub_retriever_external_services: None,
    ) -> None:
        # Arrange
        monkeypatch.setenv("SOLR_CATALOG_RO_USERNAME", "catalog-user")
        monkeypatch.setenv("SOLR_CATALOG_RO_PASSWORD", "catalog-pass")

        # Act
        args = RetrieverServiceArguments(argparse.ArgumentParser(), argv=[])

        # Assert
        assert (args.solr_user, args.solr_password) == ("catalog-user", "catalog-pass")

    @pytest.mark.integration
    def test_full_text_search_retriever_service(
        self,
        get_retriever_service_solr_parameters: dict[str, Any],
        solr_catalog_url: str,
        queue_config: tuple[Any, Any, Any],
    ) -> None:
        """Use case: Check if the message is sent to the queue"""

        queue_params = queue_config[0].queue_params
        # Define the consumer instance
        consumer_instance = ConcreteQueueConsumer(queue_params)

        ensure_queue_ready_and_purged(consumer_instance)

        assert consumer_instance.channel is not None
        logger.info(f"Purging the queue {queue_params.queue_name} before the test")

        list_documents = ["nyp.33433082002258", "not_exist_document"]

        document_retriever_service_obj = FullTextSearchRetrieverQueueService(
            queue_params,
            solr_catalog_url,
            "solr_user",
            "solr_password",
            get_retriever_service_solr_parameters,
        )

        # Service to push a message
        document_retriever_service_obj.full_text_search_retriever_service(list_documents, "item")

        # Service to consume the message
        ht_ids = drain_ht_ids(consumer_instance)
        assert ht_ids[0] == list_documents[0]

        # Clean up the queue, if the queue is already set up
        close_channel_and_connection(consumer_instance)

        # Delete the temporary files
        os.remove(queue_config[1])
        os.remove(queue_config[2])

    @pytest.mark.integration
    @pytest.mark.parametrize(
        ("ids", "by_field", "expected"),
        [
            # """Use case: Receive a list of items (ht_id) to index and retrieve the metadata from Catalog
            # We want to index only the item that appear in the list and not all the items of each record.
            # """
            pytest.param(["nyp.33433082002258"], "item", 1, id="one-item"),
            pytest.param(RECORD_HT_IDS, "item", 5, id="five-items"),
            # """Use case: Receive a list of record ids to index and retrieve the metadata from Catalog
            # We want to index all the items of each record.
            # """
            pytest.param(["008394936"], "record", 4, id="one-record"),
            pytest.param(["008394936", "100393743"], "record", 5, id="two-records"),
        ],
    )
    def test_retrieve_documents_returns_expected_item_count(
        self,
        get_document_retriever_service: FullTextSearchRetrieverQueueService,
        solr_client: HTSolrAPI,
        ids: list[str],
        by_field: str,
        expected: int,
    ) -> None:
        """Use case: Check if the number of items retrieved from Solr is as expected"""
        assert (
            len(_items_for(get_document_retriever_service, ids, by_field, solr_client)) == expected
        )

    @pytest.mark.integration
    def test_retrieve_documents_empty_result(
        self,
        get_document_retriever_service: FullTextSearchRetrieverQueueService,
        solr_client: HTSolrAPI,
    ) -> None:
        """Use case: Check of the results list is empty because the input item is not in Solr"""
        list_documents = ["this_id_does_not_exist_in_solr"]

        query = make_solr_term_query(list_documents, by_field="item")

        response = get_document_retriever_service.retrieve_documents_from_solr(query, solr_client)

        output = json.loads(response.content.decode("utf-8"))

        assert output.get("response").get("numFound") == 0

    @pytest.mark.integration
    def test_solr_is_not_working(
        self,
        get_retriever_service_solr_parameters: dict[str, Any],
        get_catalog_retriever_service_solr_fake_solr_url: HTSolrAPI,
    ) -> None:
        """Use case: retrieve_documents_from_solr raises when Solr is unreachable

        retrieve_documents_from_solr builds its request URL from self.solr_host, not from
        the solr_retriever argument's own URL (that's only used for its .send_solr_request()
        method and .auth), so the service under test needs to be the one pointed at the fake
        core, not just the HTSolrAPI client passed to it.
        """

        list_documents = ["nyp.33433082002258"]

        query = make_solr_term_query(list_documents, by_field="item")

        broken_solr_service = FullTextSearchRetrieverQueueService(
            solr_host=FAKE_CATALOG_URL,
            solr_retriever_query_params=get_retriever_service_solr_parameters,
        )

        with pytest.raises(requests.exceptions.RequestException):
            broken_solr_service.retrieve_documents_from_solr(
                query, get_catalog_retriever_service_solr_fake_solr_url
            )

    @pytest.mark.parametrize(
        "solr_host",
        [
            pytest.param(FAKE_CATALOG_URL, id="without-trailing-slash"),
            pytest.param(f"{FAKE_CATALOG_URL}/", id="with-trailing-slash"),
        ],
    )
    def test_retrieve_documents_from_solr_request_url_has_single_slash_before_query(
        self, solr_host: str
    ) -> None:
        """Use case: solr_host with trailing and without slash is handled correctly"""
        service = FullTextSearchRetrieverQueueService(
            solr_host=solr_host,
            solr_retriever_query_params={},
        )
        solr_retriever = MagicMock()
        solr_retriever.send_solr_request.return_value.status_code = 200

        service.retrieve_documents_from_solr("id:1", solr_retriever)

        assert (
            solr_retriever.send_solr_request.call_args.kwargs["solr_host"]
            == f"{FAKE_CATALOG_URL}/query"
        )


class TestMainListDocumentsRequired:
    """main() must exit 1 with `--list_documents is required` when the list is missing
    or empty, before constructing FullTextSearchRetrieverQueueService (no Solr or queue
    connection should be opened)."""

    @pytest.fixture
    def run_main(
        self, stub_retriever_external_services: None, monkeypatch: pytest.MonkeyPatch
    ) -> Callable[[list[str]], tuple[SystemExit, list[Any], MagicMock]]:
        def _run(argv: list[str]) -> tuple[SystemExit, list[Any], MagicMock]:
            monkeypatch.setattr(sys, "argv", ["retriever", "--query_field", "item", *argv])
            with (
                # Red-phase safety: today's code enters the `while True` polling loop
                # and sleeps forever; fail fast instead of hanging.
                patch("time.sleep", side_effect=AssertionError("entered polling mode")),
                patch.object(
                    retriever_service_module, "FullTextSearchRetrieverQueueService"
                ) as service_cls,
                capture_logs() as entries,
                pytest.raises(SystemExit) as exc_info,
            ):
                retriever_service_module.main()
            return exc_info.value, entries, service_cls

        return _run

    @pytest.mark.parametrize(
        "argv",
        [
            pytest.param([], id="list-documents-omitted"),
            pytest.param(["--list_documents", ""], id="list-documents-empty"),
        ],
    )
    def test_main_without_list_documents_exits_1(
        self,
        run_main: Callable[[list[str]], tuple[SystemExit, list[Any], MagicMock]],
        argv: list[str],
    ) -> None:
        exit_exc, entries, service_cls = run_main(argv)

        assert exit_exc.code == 1
        assert_log_entry(entries, event="--list_documents is required", log_level="error")
        service_cls.assert_not_called()


class TestLogHtIdsNotInCatalog:
    @staticmethod
    def _items(*ht_ids: str) -> list[CatalogItemMetadata]:
        items: list[CatalogItemMetadata] = []
        for ht_id in ht_ids:
            item = MagicMock()
            item.ht_id = ht_id
            items.append(item)
        return items

    def test_logs_error_for_each_ht_id_missing_from_catalog(self) -> None:
        with patch.object(retriever_service_module, "logger") as mock_logger:
            missing = FullTextSearchRetrieverQueueService.log_ht_ids_not_in_catalog(
                ["mdp.1", "mdp.2", "mdp.3"], self._items("mdp.1")
            )

        assert missing == {"mdp.2", "mdp.3"}
        assert mock_logger.error.call_count == 2
        logged = [call.args[0] for call in mock_logger.error.call_args_list]
        assert "mdp.2" in logged[0] and "not found in Catalog" in logged[0]
        assert "mdp.3" in logged[1] and "not found in Catalog" in logged[1]

    def test_does_not_log_when_all_ht_ids_are_returned(self) -> None:
        with patch.object(retriever_service_module, "logger") as mock_logger:
            missing = FullTextSearchRetrieverQueueService.log_ht_ids_not_in_catalog(
                ["mdp.1", "mdp.2"], self._items("mdp.1", "mdp.2")
            )

        assert missing == set()
        mock_logger.error.assert_not_called()

    def test_ht_id_with_metadata_error_is_not_reported_missing(self) -> None:
        missing = FullTextSearchRetrieverQueueService.log_ht_ids_not_in_catalog(
            ["mdp.1", "mdp.2"], self._items("mdp.1"), {"mdp.2"}
        )

        assert missing == set()


class TestRetrieverLoopMissingHtIdsCheck:
    # Infrastructure-free: Solr, the queue and the publishing step are mocked, so the test only
    # checks when the loop runs the "not found in Catalog" check.
    @staticmethod
    def _run_loop(by_field: str) -> MagicMock:
        service = FullTextSearchRetrieverQueueService(
            MagicMock(), "http://solr", "solr_user", "solr_password", {}
        )
        response = MagicMock()
        response.content = json.dumps({"response": {"docs": []}}).encode("utf-8")
        with (
            patch.object(FullTextSearchRetrieverQueueService, "get_queue_producer"),
            patch.object(retriever_service_module, "HTSolrAPI"),
            patch.object(service, "retrieve_documents_from_solr", return_value=response),
            patch.object(
                FullTextSearchRetrieverQueueService,
                "generate_chunk_metadata",
                return_value=ChunkMetadata(),
            ),
            patch.object(FullTextSearchRetrieverQueueService, "publishing_documents"),
            patch.object(
                FullTextSearchRetrieverQueueService, "log_ht_ids_not_in_catalog"
            ) as mock_check,
        ):
            service.full_text_search_retriever_service(["mdp.1", "mdp.2"], by_field)
        return mock_check

    def test_item_mode_checks_for_ht_ids_not_in_catalog(self) -> None:
        mock_check = self._run_loop("item")

        mock_check.assert_called_once_with(["mdp.1", "mdp.2"], [], {})

    def test_ht_id_query_field_checks_for_ht_ids_not_in_catalog(self) -> None:
        # --query_field defaults to "ht_id" (see retriever_arguments.py), so the check must run for it
        mock_check = self._run_loop("ht_id")

        mock_check.assert_called_once_with(["mdp.1", "mdp.2"], [], {})

    def test_record_mode_skips_the_check_because_chunk_holds_record_ids(self) -> None:
        mock_check = self._run_loop("record")

        mock_check.assert_not_called()


class TestPublishingDocuments:
    # Ids whose catalog metadata failed are never published, but they still get a failed status
    # and are counted, so the run summary accounts for them. Publish failures are logged at
    # ERROR with the ht_id (the only per-item failure record after MySQL tracking is removed).
    @staticmethod
    def _publish_one_metadata_failure() -> PublishCounts:
        return FullTextSearchRetrieverQueueService.publishing_documents(
            MagicMock(), [], {"mdp.bad": "bad item"}
        )

    @staticmethod
    def _publish_one_failed_and_one_succeeded() -> PublishCounts:
        records: list[CatalogItemMetadata] = [MagicMock(), MagicMock()]
        with (
            patch.object(
                FullTextSearchRetrieverQueueService,
                "generate_metadata",
                side_effect=[({"ht_id": "mdp.fail"}, "mdp.fail"), ({"ht_id": "mdp.ok"}, "mdp.ok")],
            ),
            patch.object(
                RetrieverServicesUtils,
                "publish_document",
                side_effect=[RuntimeError("queue down"), None],
            ),
        ):
            return FullTextSearchRetrieverQueueService.publishing_documents(MagicMock(), records)

    def test_publishing_documents_metadata_failure_counted_as_failed(self) -> None:
        counts = TestPublishingDocuments._publish_one_metadata_failure()

        assert counts == PublishCounts(failed=1)

    def test_publishing_documents_publish_failure_logs_error_with_ht_id(self) -> None:
        with capture_logs() as entries:
            TestPublishingDocuments._publish_one_failed_and_one_succeeded()

        assert any(e["log_level"] == "error" and "htid=mdp.fail" in e["event"] for e in entries), (
            entries
        )

    def test_publishing_documents_publish_failure_returns_counts(self) -> None:
        counts = TestPublishingDocuments._publish_one_failed_and_one_succeeded()

        assert counts == PublishCounts(published=1, failed=1)


class TestRetrieverPublishCounts:
    # Infrastructure-free: the counts feed the run_retriever_service_by_file summary
    # (seeded = published to the queue, errors = publish failures).

    def test_full_text_search_retriever_service_two_chunks_returns_summed_counts(self) -> None:
        service = FullTextSearchRetrieverQueueService(
            MagicMock(), "http://solr", "solr_user", "solr_password", {}
        )
        # Patch the retrieve_documents_from_solr method to return a mock response with no documents
        response = MagicMock()
        response.content = json.dumps({"response": {"docs": []}}).encode("utf-8")
        with (
            patch.object(retriever_service_module, "SOLR_BATCH_SIZE", 1),
            patch.object(FullTextSearchRetrieverQueueService, "get_queue_producer"),
            patch.object(retriever_service_module, "HTSolrAPI"),
            patch.object(service, "retrieve_documents_from_solr", return_value=response),
            patch.object(
                FullTextSearchRetrieverQueueService,
                "generate_chunk_metadata",
                return_value=ChunkMetadata(),
            ),
            patch.object(
                FullTextSearchRetrieverQueueService, "log_ht_ids_not_in_catalog", return_value=set()
            ),
            patch.object(
                FullTextSearchRetrieverQueueService,
                "publishing_documents",
                side_effect=[
                    retriever_service_module.PublishCounts(published=1, failed=0),
                    retriever_service_module.PublishCounts(published=0, failed=1),
                ],
            ),
        ):
            counts = service.full_text_search_retriever_service(["mdp.1", "mdp.2"], "item")

        assert counts == retriever_service_module.PublishCounts(published=1, failed=1)

    def test_full_text_search_retriever_service_item_mode_counts_failed_and_not_found(
        self,
    ) -> None:
        # mdp.2's metadata failed and mdp.3 is not in Catalog: neither is published, both counted.
        service = FullTextSearchRetrieverQueueService(
            MagicMock(), "http://solr", "solr_user", "solr_password", {}
        )
        response = MagicMock()
        response.content = json.dumps({"response": {"docs": []}}).encode("utf-8")
        with (
            patch.object(FullTextSearchRetrieverQueueService, "get_queue_producer"),
            patch.object(retriever_service_module, "HTSolrAPI"),
            patch.object(service, "retrieve_documents_from_solr", return_value=response),
            patch.object(
                FullTextSearchRetrieverQueueService,
                "generate_chunk_metadata",
                return_value=ChunkMetadata(failed={"mdp.2": "bad item"}),
            ),
        ):
            counts = service.full_text_search_retriever_service(["mdp.2", "mdp.3"], "item")

        assert counts == PublishCounts(failed=1, not_found=1)

    def test_run_retriever_service_threads_failed_batch_counts_its_ids_as_failed(self) -> None:
        service = MagicMock()
        service.full_text_search_retriever_service.side_effect = [
            retriever_service_module.PublishCounts(published=2, failed=0),
            RuntimeError("Solr down"),
        ]

        # max_workers=2 splits the 4 ids into two batches of 2. Whichever batch gets the error,
        # the totals are the same.
        counts = retriever_service_module.run_retriever_service_threads(
            ["mdp.1", "mdp.2", "mdp.3", "mdp.4"], "item", service, 2
        )

        assert counts == retriever_service_module.PublishCounts(published=2, failed=2)
