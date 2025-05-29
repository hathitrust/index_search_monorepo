import tempfile
from pathlib import Path

import pytest
from conftest import get_rabbitmq_host_name
from document_retriever_service.ht_status_retriever_service import get_non_processed_ids
from document_retriever_service.run_retriever_service_by_file import retrieve_documents_by_file

#current = os.path.dirname(__file__)

current_dir = Path(__file__).parent

rabbit_mq_host = get_rabbitmq_host_name()


@pytest.fixture()
def get_input_file():
    """TXT file containing the list of items to process"""
    file_path = current_dir.parent / "list_htids_indexer_test.txt"

    return file_path #os.path.join(current, "list_htids_indexer_test.txt")


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

    @pytest.mark.parametrize("retriever_parameters", [{"user": "guest", "password": "guest", "host": rabbit_mq_host,
                                                       "queue_name": "test_producer_queue",
                                                       "requeue_message": False,
                                                       "query_field": "item",
                                                       "batch_size": 1}])
    def test_run_retriever_service_by_file(self, retriever_parameters, get_input_file, get_status_file,
                                           consumer_instance, solr_catalog_url, get_retriever_service_solr_parameters):

        # Clean up the queue
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)

        retrieve_documents_by_file(retriever_parameters["queue_name"],
                                   retriever_parameters["host"],
                                   retriever_parameters["user"],
                                   retriever_parameters["password"],
                                   retriever_parameters["query_field"],
                                   solr_catalog_url,
                                   'solr_user',
                                   'solr_password',
                                   get_retriever_service_solr_parameters,
                                   get_input_file,
                                   get_status_file,
                                   parallelize=False)

        assert 9 == consumer_instance.conn.get_total_messages()

        # Clean up the queue
        consumer_instance.conn.ht_channel.queue_purge(consumer_instance.queue_name)
