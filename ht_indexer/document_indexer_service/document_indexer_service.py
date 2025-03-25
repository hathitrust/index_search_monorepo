import argparse
import inspect
import os
import sys
import time

from ht_queue_service.queue_multiple_consumer import QueueMultipleConsumer, positive_acknowledge
from ht_utils import ht_utils
from ht_utils.ht_logger import get_ht_logger
from ht_indexer_api.ht_indexer_api import HTSolrAPI

logger = get_ht_logger(name=__name__)

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

class DocumentIndexerQueueService(QueueMultipleConsumer):

    def __init__(self, solr_api_full_text: HTSolrAPI, queue_parameters: dict):

        # Call the parent class constructor that initializes the connection to the queue
        super().__init__(queue_parameters.get("queue_user"), queue_parameters.get("queue_pass"),
                         queue_parameters.get("queue_host"),
                         queue_parameters.get("queue_name"),
                         queue_parameters.get("requeue_message"),
                        queue_parameters.get("batch_size"))

        self.solr_api_full_text = solr_api_full_text
        self.queue_parameters = queue_parameters

    def requeue_failed_messages(self, messages=None, delivery_tags=None, error: Exception = None):
        """Requeue failed messages into the Dead Letter Queue."""

        logger.info(f"Send total_messages={len(delivery_tags)} to the {self.queue_name}_dead_letter_queue.")

        for message, delivery_tag in zip(messages, delivery_tags):
            error_info = ht_utils.get_error_message_by_document("DocumentIndexerService", error, message)
            logger.error(f"Failed process=indexing error_detail={error_info}")
            self.reject_message(self.conn.ht_channel, delivery_tag)

    def process_batch(self, batch: list, delivery_tags: list):
        """Process a batch of messages from the queue.
        If the indexing process is successful, acknowledge all the messages in the batch.
        If the indexing process fails, requeue all the failed messages to the Dead Letter Queue.
        The error on this service is because Solr is not available.

        :param batch: List of messages to process
        :param delivery_tags: List of delivery tags to acknowledge
        """
        # TODO - Implement the process to validate if the message is well formatted to index in Solr.
        # When the validation will be in place, instead of sending all the message to the dead letter queue,
        # we should add the logic to just sent the message that are not well formatted to the dead letter queue.
        start_time = time.time()

        try:
            response = self.solr_api_full_text.index_documents(batch)
            logger.info(
                f"Success process=indexing {len(batch)} items."
                f"Operation status: {response.status_code} Time={time.time() - start_time:.10f} ")

            response.raise_for_status()

            # Acknowledge all messages in batch
            for delivery_tag in delivery_tags:
                positive_acknowledge(self.conn.ht_channel, delivery_tag)

        except Exception as e:
            logger.info(f"Failed process=indexing with error={e}")
            failed_messages = batch #self.batch
            failed_messages_tags = delivery_tags.copy()
            # Requeue the full list of failed messages to the Dead Letter Queue
            self.requeue_failed_messages(failed_messages, failed_messages_tags, e)

        batch.clear()
        delivery_tags.clear()
        return True

def start_service(solr_api_full_text: HTSolrAPI, queue_parameters: dict):
    document_indexer_queue_service = DocumentIndexerQueueService(solr_api_full_text, queue_parameters)
    document_indexer_queue_service.start_consuming()

def main():
    parser = argparse.ArgumentParser()

    from document_indexer_service.indexer_arguments import IndexerServiceArguments
    init_args_obj = IndexerServiceArguments(parser)

    start_service(init_args_obj.solr_api_full_text, init_args_obj.queue_parameters)

if __name__ == "__main__":
    main()
