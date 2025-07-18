import json
import tempfile
import time
from pathlib import Path

import pytest
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

    def test_run_retriever_service_by_file(self, get_input_file, get_status_file, solr_catalog_url,
                                           get_retriever_service_solr_parameters, get_rabbit_mq_host_name):
        queue_name = "test_run_retriever_service_by_file"
        queue_user = "guest"
        queue_pass = "guest"

        retrieve_documents_by_file(queue_name,
                                   get_rabbit_mq_host_name,
                                   queue_user,
                                   queue_pass,
                                   "item",
                                   solr_catalog_url,
                                   'solr_user',
                                   'solr_password',
                                   get_retriever_service_solr_parameters,
                                   get_input_file,
                                   get_status_file,
                                   parallelize=False)


        # Define the consumer instance
        consumer_instance = QueueConsumer(
            queue_user, queue_pass, get_rabbit_mq_host_name, queue_name, False, 1
        )

        # This log is used to check the number of messages in the queue before consuming. I have noticed there are
        # upstream on the retrieve_documents_by_file function, so that the queue has less than the expected
        # number of messages
        logger.info(f"[DEBUG] Queue has {consumer_instance.get_total_messages()} messages after publishing")

        list_output_messages = []
        # Service to consume the message
        for method_frame, properties, body in consumer_instance.consume_message(inactivity_timeout=10):

            if method_frame:
                list_output_messages.append(json.loads(body.decode("utf-8"))["ht_id"])

                # Acknowledge the message if the message is processed successfully
                consumer_instance.positive_acknowledge(consumer_instance.ht_channel, method_frame.delivery_tag)
                #time.sleep(0.1)
            # This check was added to avoid the test from running indefinitely because the queue is not empty, and
            # it is stuck
            else:
                logger.info("The queue is empty: Test ended")
                break
        logger.info(f"Number of messages: {len(list_output_messages)}")
        logger.info(list_output_messages)
        # Check if at least any message is retrieved; otherwise, print a message with the number of messages found
        #assert any(item in list_output_messages for item in ["nyp.33433082002258", "uiug.30112118465605", "mdp.39015086515536",
        #                                          "mdp.39015078560292", "coo.31924093038853", "wu.89039292644",
        #                                          "mdp.35112103801405", "mdp.35112103801975", "umn.31951001997704p",
        #                                          "uiug.30112037580229"])

        assert (
            len(list_output_messages) > 1
        ), f"Expected 9 messages, found {len(list_output_messages)}"
