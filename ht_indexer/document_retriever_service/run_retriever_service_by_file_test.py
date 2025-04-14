import pytest
import os

from document_retriever_service.run_retriever_service_by_file import retrieve_documents_by_file
from document_retriever_service.ht_status_retriever_service import get_non_processed_ids
import tempfile

current = os.path.dirname(__file__)


@pytest.fixture()
def get_input_file():
    """TXT file containing the list of items to process"""
    return os.path.join(current, "list_htids_indexer_test.txt")


@pytest.fixture()
def get_status_file():

    """Creates and returns a temporary TXT file to store the status of items to process"""
    tmpfile_status = tempfile.NamedTemporaryFile(mode="w+", delete=False)
    return tmpfile_status.name


class TestRunRetrieverServiceByFile:

    def test_get_non_processed_ids(self, get_input_file, get_status_file):
        with open(get_input_file) as f:
            list_ids = f.read().splitlines()

            ids2process, processed_ids = get_non_processed_ids(get_status_file, list_ids)
            assert len(ids2process) == 12
            assert len(processed_ids) == 0

    @pytest.mark.parametrize("retriever_parameters", [{"solr_api": "http://solr-sdr-catalog:9033/solr/#/catalog/",
                                                       "user": "guest", "password": "guest", "host": "rabbitmq",
                                                       "queue_name": "test_producer_queue",
                                                       "requeue_message": False,
                                                       "query_field": "item",
                                                       "start": 0,
                                                       "rows": 100,
                                                       "batch_size": 1}])
    def test_run_retriever_service_by_file(self, retriever_parameters, get_input_file, get_status_file,
                                           consumer_instance):
        parallelize = False
        nthreads = None

        # Clean up the queue
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)

        retrieve_documents_by_file(retriever_parameters["solr_api"],
                                   retriever_parameters["queue_name"],
                                   retriever_parameters["host"],
                                   retriever_parameters["user"],
                                   retriever_parameters["password"],
                                   get_input_file,
                                   retriever_parameters["query_field"],
                                   retriever_parameters["start"],
                                   retriever_parameters["rows"],
                                   get_status_file,
                                   parallelize,
                                   nthreads)

        assert 9 == consumer_instance.conn.get_total_messages()

        # Clean up the queue
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)
