import pytest
import json
import os

from catalog_metadata.catalog_metadata import CatalogRecordMetadata, CatalogItemMetadata
from document_retriever_service.catalog_retriever_service import CatalogRetrieverService
from ht_queue_service.queue_consumer import QueueConsumer
from ht_queue_service.queue_producer import QueueProducer

current = os.path.dirname(__file__)


# Fixtures to retrieve the catalog record
# Retrieve JSON file to create a dictionary with a catalog record
@pytest.fixture()
def get_record_data():
    """JSON file containing the catalog record"""
    with open(os.path.join(current, "catalog_metadata/data/catalog.json"), "r", ) as file:
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


# CatalogRetrieverService object to retrieve the catalog record
@pytest.fixture
def get_catalog_retriever_service(solr_api_url):
    return CatalogRetrieverService(solr_api_url)


@pytest.fixture
def solr_api_url():
    return "http://solr-sdr-catalog:9033/solr/#/catalog/"


# Fixtures to instantiate the queue consumer and producer
@pytest.fixture
def retriever_parameters(request):
    """
    This function is used to create the parameters for the queue
    """
    return request.param


@pytest.fixture
def consumer_instance(retriever_parameters):
    """
    This function is used to consume messages from the queue
    """

    return QueueConsumer(retriever_parameters["user"], retriever_parameters["password"],
                         retriever_parameters["host"], retriever_parameters["queue_name"],
                         retriever_parameters["requeue_message"])


@pytest.fixture
def producer_instance(retriever_parameters):
    """
    This function is used to generate a message to the queue
    """

    return QueueProducer(retriever_parameters["user"], retriever_parameters["password"],
                         retriever_parameters["host"], retriever_parameters["queue_name"])
