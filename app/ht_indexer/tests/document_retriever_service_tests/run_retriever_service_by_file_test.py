import json
import os
import tempfile
from pathlib import Path

import pytest

from conftest import create_test_queue_config
from document_retriever_service.ht_status_retriever_service import get_non_processed_ids
from document_retriever_service.run_retriever_service_by_file import retrieve_documents_by_file
from ht_queue_service.queue_consumer import QueueConsumer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

current_dir = Path(__file__).parent


@pytest.fixture()
def get_input_file():
    """TXT file containing the list of items to process"""
    file_path = current_dir.parent / "list_htids_indexer_test.txt"

    return file_path


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

    def test_run_retriever_service_by_file(self, get_input_file, get_status_file, solr_catalog_url,
                                           get_retriever_service_solr_parameters, get_global_queue_config,
                                           get_app_queue_config):
        queue_name = "test_run_retriever_service_by_file"
        batch_size = 1
        requeue_message = False

        producer_queue_config, global_path, app_path = create_test_queue_config(get_global_queue_config,
                                                                                get_app_queue_config,
                                                                                queue_name,
                                                                                batch_size=batch_size,
                                                                                requeue_message=requeue_message)



        retrieve_documents_by_file(producer_queue_config.queue_params,
                                    "item",
                                   solr_catalog_url,
                                   'solr_user',
                                   'solr_password',
                                   get_retriever_service_solr_parameters,
                                   get_input_file,
                                   get_status_file,
                                   False)

        consumer_instance = QueueConsumer(producer_queue_config.queue_params)

        list_output_messages = []
        # Service to consume the message
        for method_frame, properties, body in consumer_instance.consume_message(inactivity_timeout=5):
            if method_frame:
                list_output_messages.append(json.loads(body.decode("utf-8"))["ht_id"])

                # Acknowledge the message if the message is processed successfully
                consumer_instance.positive_acknowledge(consumer_instance.channel, method_frame.delivery_tag)
            else:
                logger.info("The queue is empty: Test ended")
                break

        logger.info(f"Number of messages: {len(list_output_messages)}")
        logger.info(list_output_messages)

        assert all(item in list_output_messages for item in ["nyp.33433082002258",
                                                             "uiug.30112118465605",
                                                             "mdp.39015086515536",
                                                             "umn.31951001997704p",
                                                             "wu.89039292644",
                                                             "coo.31924093038853",
                                                             "mdp.35112103801405",
                                                             "mdp.35112103801975",
                                                             "uiug.30112037580229"])

        consumer_instance.channel.close()
        consumer_instance.channel_creator.connection.queue_connection.close()

        # Delete the temporary files
        os.remove(global_path)
        os.remove(app_path)
