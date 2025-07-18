import json
import os
import uuid

import pytest
from catalog_metadata.catalog_metadata import CatalogItemMetadata, CatalogRecordMetadata
from ht_utils.ht_utils import get_solr_url

current = os.path.dirname(__file__)

@pytest.fixture
def get_rabbit_mq_host_name():
    """
    This function is used to create the host name for the RabbitMQ
    """
    return  "rabbitmq" # "localhost" # #

@pytest.fixture
def get_retriever_service_solr_parameters():
    return {'q': '*:*','rows': 10, 'wt': 'json'}

# Fixtures to retrieve the catalog record
# Retrieve JSON file to create a dictionary with a catalog record
@pytest.fixture()
def get_record_data():
    """JSON file containing the catalog record"""
    with open(os.path.join(current, "catalog_metadata_tests/data/catalog.json"), ) as file:
        data = json.load(file)
    return data


# Use the catalog record to create a CatalogRecordMetadata object
@pytest.fixture()
def get_catalog_record_metadata(get_record_data):
    return CatalogRecordMetadata(get_record_data)


# Create a CatalogItemMetadata object with the catalog record and the ht_id of the item
@pytest.fixture()
def get_item_metadata(get_record_data: dict, get_catalog_record_metadata: CatalogRecordMetadata):
    return CatalogItemMetadata("mdp.39015078560292", get_catalog_record_metadata)

@pytest.fixture
def solr_catalog_url():
    return get_solr_url()

@pytest.fixture
def random_queue_name():
    return f"test_queue_{uuid.uuid4().hex[:8]}"