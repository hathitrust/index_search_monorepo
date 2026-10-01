import argparse
import sys
import time
from typing import Any

from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_queue_service.queue_config import QueueParams
from ht_queue_service.queue_multiple_consumer import QueueMultipleConsumer
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import get_error_message_by_document, get_queue_message_id
from pika.adapters.blocking_connection import BlockingChannel

from .indexer_arguments import IndexerServiceArguments


class DocumentIndexerQueueService(QueueMultipleConsumer):
    def __init__(self, solr_api_full_text: HTSolrAPI, queue_params: QueueParams):
        """Initialize the Document Indexer Queue Service.
        :param solr_api_full_text: The Solr API client for full-text indexing
        :param queue_params: The object with the queue parameters
        """
        # Call the parent class constructor that initializes the connection to the queue
        super().__init__(queue_params)
        self.solr_api_full_text = solr_api_full_text
        self.logger = get_ht_logger(__file__)

    def requeue_failed_messages(
        self,
        messages: list[dict[str, Any]],
        delivery_tags: list[int],
        error: Exception,
        channel: BlockingChannel | None,
    ) -> None:
        """Requeue failed messages into the Dead Letter Queue.
        :param messages: List of messages that failed to process
        :param delivery_tags: List of delivery tags corresponding to the messages
        :param error: The exception that caused the failure
        :param channel: The channel to use for rejecting messages
        """
        if channel is None:
            raise RuntimeError("Unable to establish a RabbitMQ channel")

        self.logger.info(
            f"Send total_messages={len(delivery_tags)} to the {self.queue_manager.dead_letter_queue_name}."
        )

        for message, delivery_tag in zip(messages, delivery_tags, strict=False):
            error_info = get_error_message_by_document("DocumentIndexerService", error, message)
            self.logger.error("Failed", process="indexing", error_detail=error_info)
            self.reject_message(channel, delivery_tag)

    def process_batch(self, batch: list[dict[str, Any]], delivery_tags: list[int]) -> bool:
        """Process a batch of messages from the queue.
        If the indexing process is successful, acknowledge all the messages in the batch.
        If the indexing process fails, requeue all the failed messages to the Dead Letter Queue.
        The error on this service is because Solr is not available.

        :param batch: List of messages to process
        :param delivery_tags: List of delivery tags to acknowledge
        """
        # TODO - Implement the process to validate if the message is well formatted to index in Solr.
        # When the validation is in place, instead of sending all the messages to the dead letter queue,
        # we should add the logic to just sent the message that are not well formatted to the dead letter queue.
        if self.channel is None:
            raise RuntimeError("Unable to establish a RabbitMQ channel")
        start_time = time.time()

        success = True
        try:
            response = self.solr_api_full_text.index_documents(batch)

            response.raise_for_status()

            for i in batch:
                self.logger.info("Indexed", ht_id=get_queue_message_id(i))

            self.logger.info(
                "Success",
                process="indexing",
                item_count=len(batch),
                operation_status=response.status_code,
                elapsed_time=time.time() - start_time,
            )

            # Acknowledge all messages in batch
            for delivery_tag in delivery_tags:
                self.positive_acknowledge(self.channel, delivery_tag)

        except Exception as e:
            self.logger.info(f"Failed process=indexing with error={e}")
            success = False
            failed_messages = batch  # self.batch
            failed_messages_tags = delivery_tags.copy()
            # Requeue the full list of failed messages to the Dead Letter Queue
            self.requeue_failed_messages(failed_messages, failed_messages_tags, e, self.channel)

        batch.clear()
        delivery_tags.clear()
        return success


def start_service(solr_api_full_text: HTSolrAPI, queue_params: QueueParams) -> bool:
    document_indexer_queue_service = DocumentIndexerQueueService(solr_api_full_text, queue_params)
    get_ht_logger().info(f"Starting Document Indexer Service with queue: {queue_params.queue_name}")
    # Start consuming messages from the queue
    return document_indexer_queue_service.start_consuming()


def main() -> None:
    parser = argparse.ArgumentParser()

    init_args_obj = IndexerServiceArguments(parser)

    if not start_service(init_args_obj.solr_api_full_text, init_args_obj.queue_config.queue_params):
        # The error was already logged by start_consuming; exit non-zero so the orchestrator restarts us
        logger.error("[!] Consumer stopped because of an error. Exiting")
        sys.exit(1)


if __name__ == "__main__":
    main()
