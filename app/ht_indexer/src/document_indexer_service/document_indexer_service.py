import argparse
import time
from typing import Any

import requests
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_queue_service.queue_config import QueueParams
from ht_queue_service.queue_multiple_consumer import QueueMultipleConsumer
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import get_error_message_by_document
from pika.adapters.blocking_connection import BlockingChannel

from .failure_classifier import FailureKind, classify_failure
from .indexer_arguments import IndexerServiceArguments

logger = get_ht_logger(name=__name__)


class DocumentIndexerQueueService(QueueMultipleConsumer):
    def __init__(self, solr_api_full_text: HTSolrAPI, queue_params: QueueParams):
        """Initialize the Document Indexer Queue Service.
        :param solr_api_full_text: The Solr API client for full-text indexing
        :param queue_params: The object with the queue parameters
        """
        # Call the parent class constructor that initializes the connection to the queue
        super().__init__(queue_params)
        self.solr_api_full_text = solr_api_full_text

    def _index(self, documents: list[dict[str, Any]]) -> None:
        """Send documents to Solr in one request. Raises if the request or the response fails."""
        start_time = time.time()
        response = self.solr_api_full_text.index_documents(documents)
        response.raise_for_status()
        logger.info(
            f"Success process=indexing {len(documents)} items. "
            f"Operation status: {response.status_code} Time={time.time() - start_time:.10f} "
        )

    def _retry(
        self, message: dict[str, Any], delivery_tag: int, error: Exception, channel: BlockingChannel
    ) -> None:
        """Leave a message on the original queue to be tried again; the message is not at fault."""
        logger.warning(f"Retry process=indexing ht_id={message.get('ht_id')} error={error}")
        self.retry_message(channel, delivery_tag)

    def _dead_letter(
        self, message: dict[str, Any], delivery_tag: int, error: Exception, channel: BlockingChannel
    ) -> None:
        """Send a message that can never be indexed to the Dead Letter Queue."""
        error_info = get_error_message_by_document("DocumentIndexerService", error, message)
        logger.error(
            f"Failed process=indexing sent to {self.queue_manager.dead_letter_queue_name} "
            f"error_detail={error_info}"
        )
        self.dead_letter_message(channel, delivery_tag)

    def process_batch(self, batch: list[dict[str, Any]], delivery_tags: list[int]) -> bool:
        """Process a batch of messages from the queue.

        If the whole batch is indexed, acknowledge every message.
        If it fails, work out why (see failure_classifier):
        * Solr is unreachable or rejects our credentials: put the whole batch back on the queue.
        * Otherwise try each document on its own. Acknowledge the ones that work, dead-letter the
          ones Solr rejects as bad, and put back the ones that hit a temporary error.

        :param batch: List of messages to process
        :param delivery_tags: List of delivery tags to acknowledge
        :return: True if every message was acknowledged, False otherwise
        """
        if self.channel is None:
            raise RuntimeError("Unable to establish a RabbitMQ channel")
        channel = self.channel

        try:
            self._index(batch)
        except Exception as e:
            logger.error(
                f"Failed process=indexing scope=batch total_messages={len(batch)} error={e}"
            )
            all_acked = self._handle_failed_batch(batch, delivery_tags, e, channel)
        else:
            for delivery_tag in delivery_tags:
                self.positive_acknowledge(channel, delivery_tag)
            all_acked = True

        batch.clear()
        delivery_tags.clear()
        return all_acked

    def _handle_failed_batch(
        self,
        batch: list[dict[str, Any]],
        delivery_tags: list[int],
        error: Exception,
        channel: BlockingChannel,
    ) -> bool:
        """Decide what to do with each message after the batch request failed.
        :return: True if every message was acknowledged, False otherwise
        """
        if _solr_cannot_be_used(error):
            # Posting each document alone would fail the same way.
            for message, delivery_tag in zip(batch, delivery_tags, strict=True):
                self._retry(message, delivery_tag, error, channel)
            return False

        all_acked = True
        # Set once Solr stops being usable mid-way, so the rest are put back without a request.
        blocked_by: Exception | None = None
        for message, delivery_tag in zip(batch, delivery_tags, strict=True):
            if blocked_by is not None:
                all_acked = False
                self._retry(message, delivery_tag, blocked_by, channel)
                continue
            try:
                self._index([message])
            except Exception as doc_error:
                all_acked = False
                if classify_failure(doc_error) is FailureKind.PERMANENT:
                    self._dead_letter(message, delivery_tag, doc_error, channel)
                else:
                    self._retry(message, delivery_tag, doc_error, channel)
                    if _solr_cannot_be_used(doc_error):
                        blocked_by = doc_error
            else:
                self.positive_acknowledge(channel, delivery_tag)
        return all_acked


def _solr_cannot_be_used(error: Exception) -> bool:
    """True when retrying a single document is pointless: Solr is unreachable (no HTTP answer at
    all) or is refusing our credentials. A 5xx answer is not included, since one bad document
    can cause it.
    """
    kind = classify_failure(error)
    if kind is FailureKind.CONFIG_ERROR:
        return True
    return kind is FailureKind.TRANSIENT and not isinstance(error, requests.exceptions.HTTPError)


def start_service(solr_api_full_text: HTSolrAPI, queue_params: QueueParams) -> None:
    document_indexer_queue_service = DocumentIndexerQueueService(solr_api_full_text, queue_params)
    logger.info(f"Starting Document Indexer Service with queue: {queue_params.queue_name}")
    # Start consuming messages from the queue
    document_indexer_queue_service.start_consuming()


def main() -> None:
    parser = argparse.ArgumentParser()

    init_args_obj = IndexerServiceArguments(parser)

    start_service(init_args_obj.solr_api_full_text, init_args_obj.queue_config.queue_params)


if __name__ == "__main__":
    main()
