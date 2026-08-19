import copy
import json
import os
import uuid
from pathlib import Path
from typing import Any

import pytest
from catalog_metadata.catalog_metadata import CatalogItemMetadata, CatalogRecordMetadata
from ht_queue_service.queue_config import QueueConfig
from ht_utils.ht_utils import create_temporary_yaml_file, get_solr_url

current = os.path.dirname(__file__)


@pytest.fixture
def get_global_queue_config() -> dict[str, Any]:
    """
    Creates an in-memory YAML file from a base dictionary,
    applies updates, and returns a file-like object or path.
    """

    return {
        "queue": {
            "host": "rabbitmq",  # "localhost", #, #
            "port": 5672,
            "user": "guest",
            "password": "guest",
        }
    }


@pytest.fixture
def get_app_queue_config() -> dict[str, Any]:
    """
    This function is used to create the application configuration
    """
    return {
        "queue": {
            "queue_name": None,
            "batch_size": 1,
            "requeue_message": False,
            "exchange_type": "direct",
            "durable": True,
            "auto_delete": False,
            "exclusive": False,
            "heartbeat": 60,
            "connection_timeout": 10,
            "retry_interval": 5,
            "shutdown_on_empty_queue": False,
        }
    }


def create_test_queue_config(
    global_config: dict[str, Any],
    app_config: dict[str, Any],
    queue_name: str,
    batch_size: int = 1,
    requeue_message: bool = False,
    shutdown_on_empty_queue: bool = False,
) -> tuple[QueueConfig, str, str]:

    global_config_file_path = create_temporary_yaml_file(global_config)
    config = copy.deepcopy(app_config)
    config["queue"].update(
        {
            "queue_name": queue_name,
            "batch_size": batch_size,
            "requeue_message": requeue_message,
            "shutdown_on_empty_queue": shutdown_on_empty_queue,
        }
    )
    app_config_file_path = create_temporary_yaml_file(config)
    queue_config = QueueConfig(Path(global_config_file_path), Path(app_config_file_path))
    return queue_config, global_config_file_path, app_config_file_path


@pytest.fixture
def get_rabbit_mq_host_name() -> str:
    """
    This function is used to create the host name for the RabbitMQ
    """
    return "rabbitmq"  # "localhost"


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
    return get_solr_url()


@pytest.fixture
def random_queue_name() -> str:
    return f"test_queue_{uuid.uuid4().hex[:8]}"
