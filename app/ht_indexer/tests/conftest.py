import json
import os
import uuid
from typing import Any, Protocol

import pytest
from catalog_metadata.catalog_metadata import CatalogItemMetadata, CatalogRecordMetadata
from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_manager import QueueManager
from ht_queue_service.queue_multiple_consumer import QueueMultipleConsumer
from ht_queue_service.queue_settings import QueueSettings
from ht_utils.ht_env_config import ht_env_config
from pika.adapters.blocking_connection import BlockingChannel

current = os.path.dirname(__file__)

SOLR_CATALOG_CREDENTIAL_VARS = (
    "SOLR_CATALOG_RO_USERNAME",
    "SOLR_CATALOG_RO_PASSWORD",
)


class ConcreteQueueConsumer(QueueMultipleConsumer):
    """Minimal concrete QueueMultipleConsumer for tests that only need to purge,
    reconnect, or drain a single message via consume_dead_letter_messages() --
    not batch processing. process_batch is never invoked by those call paths;
    it exists only to satisfy QueueMultipleConsumer's ABC contract.
    """

    def process_batch(self, batch: list[Any], delivery_tag: list[int]) -> bool:
        return True


class QueueTestSettings(QueueSettings):
    queue_name: str = "default_test_queue"
    batch_size: int = 1
    requeue_message: bool = False
    exchange_type: str = "direct"
    durable: bool = True
    auto_delete: bool = False
    exclusive: bool = False
    heartbeat: int = 60
    connection_timeout: int = 10
    retry_interval: int = 5
    shutdown_on_empty_queue: bool = False


@pytest.fixture
def get_retriever_service_solr_parameters() -> dict[str, Any]:
    return {"q": "*:*", "rows": 10, "wt": "json"}


# Fixtures to retrieve the catalog record
# Retrieve JSON file to create a dictionary with a catalog record
@pytest.fixture()
def get_record_data() -> dict[str, Any]:
    """JSON file containing the catalog record"""
    with open(
        os.path.join(current, "catalog_metadata_tests/data/catalog.json"),
    ) as file:
        data: dict[str, Any] = json.load(file)
    return data


# Use the catalog record to create a CatalogRecordMetadata object
@pytest.fixture()
def get_catalog_record_metadata(get_record_data: dict[str, Any]) -> CatalogRecordMetadata:
    return CatalogRecordMetadata(get_record_data)


# Create a CatalogItemMetadata object with the catalog record and the ht_id of the item
@pytest.fixture()
def get_item_metadata(
    get_record_data: dict[str, Any], get_catalog_record_metadata: CatalogRecordMetadata
) -> CatalogItemMetadata:
    return CatalogItemMetadata("mdp.39015078560292", get_catalog_record_metadata)


@pytest.fixture
def solr_catalog_url() -> str:
    return ht_env_config.solr_catalog_ro.url


@pytest.fixture
def random_queue_name() -> str:
    return f"test_queue_{uuid.uuid4().hex[:8]}"


class QueueServiceLike(Protocol):
    """Structural type for QueueProducer/QueueMultipleConsumer -- they don't
    share a base class, but both expose this same shape."""

    channel: BlockingChannel | None
    channel_creator: ChannelCreator
    queue_manager: QueueManager


def ensure_queue_ready_and_purged(service: QueueServiceLike) -> None:
    """Make sure the queue exists, then start the test from an empty queue.

    This is the ~5-line "is it ready, reconnect if not, purge" block every queue
    test re-implemented inline before doing anything else.
    """
    if not service.queue_manager.is_ready(service.channel):
        # is_ready() leaves the channel closed when the queue is missing: open a new one
        service.channel = service.channel_creator.get_channel()
        assert service.channel is not None
        service.channel.confirm_delivery()  # same mode as QueueProducer; harmless for consumers
        service.queue_manager.set_up_queue(service.channel)
    assert service.channel is not None
    service.channel.queue_purge(service.queue_manager.queue_name)


def close_channel_and_connection(service: QueueServiceLike) -> None:
    """Close the channel and its underlying connection -- the teardown half of
    the ritual, called at the end of (or partway through) a test.
    """
    assert service.channel is not None
    service.channel.close()
    assert service.channel_creator.connection.queue_connection is not None
    service.channel_creator.connection.queue_connection.close()


def drain_ht_ids(consumer: QueueMultipleConsumer, timeout: int = 5) -> list[str]:
    """Consume all messages from the queue and return their ht_ids."""
    channel = consumer.channel
    assert channel is not None
    ht_ids: list[str] = []
    for method_frame, _properties, body in consumer.consume_dead_letter_messages(
        channel,
        inactivity_timeout=timeout,
        queue_name=consumer.queue_manager.queue_name,
    ):
        if method_frame:
            ht_ids.append(json.loads(body.decode("utf-8"))["ht_id"])
            consumer.positive_acknowledge(channel, method_frame.delivery_tag)
        else:
            break
    return ht_ids
