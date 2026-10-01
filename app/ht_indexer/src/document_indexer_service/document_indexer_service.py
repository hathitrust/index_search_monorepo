import argparse
import time
from typing import Any

from catalog_metadata.ht_indexer_config import ProcessingStatus
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_indexer_monitoring.ht_indexer_tracktable import PROCESSING_STATUS_TABLE_NAME
from ht_queue_service.queue_config import QueueParams
from ht_queue_service.queue_multiple_consumer import QueueMultipleConsumer
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_mysql import HtMysql
from ht_utils.ht_utils import (
    get_current_time,
    get_error_message_by_document,
    get_general_error_message,
)
from pika.adapters.blocking_connection import BlockingChannel

from .indexer_arguments import IndexerServiceArguments

logger = get_ht_logger(name=__name__)

MYSQL_COLUMN_UPDATE = "indexer_status"
# No status guard: the indexer is the terminal stage and is authoritative on the final state.
# Its success proves the document is in Solr; its failure is the last word. No downstream
# stage writes status after it, so no race guard is needed. Success clears error, so an item
# that failed upstream and was later indexed doesn't keep a stale error on a completed row.
SUCCESS_UPDATE_STATUS = (
    f"UPDATE {PROCESSING_STATUS_TABLE_NAME} SET "
    f"{MYSQL_COLUMN_UPDATE} = :indexer_status, processed_at = :processed_at, "
    f"error = NULL, status = :status WHERE ht_id = :ht_id"
)
FAILURE_UPDATE_STATUS = (
    f"UPDATE {PROCESSING_STATUS_TABLE_NAME} SET "
    f"{MYSQL_COLUMN_UPDATE} = :indexer_status, processed_at = :processed_at, "
    f"error = :error, status = :status WHERE ht_id = :ht_id"
)


class DocumentIndexerQueueService(QueueMultipleConsumer):
    def __init__(
        self,
        solr_api_full_text: HTSolrAPI,
        db_conn: HtMysql,
        queue_params: QueueParams,
    ):
        """Initialize the Document Indexer Queue Service.
        :param solr_api_full_text: The Solr API client for full-text indexing
        :param db_conn: MySQL connection used to record indexer_status per item
        :param queue_params: The object with the queue parameters
        """
        # Call the parent class constructor that initializes the connection to the queue
        super().__init__(queue_params)
        self.solr_api_full_text = solr_api_full_text
        self.db_conn = db_conn

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

        logger.info(
            f"Send total_messages={len(delivery_tags)} to the {self.queue_manager.dead_letter_queue_name}."
        )

        for message, delivery_tag in zip(messages, delivery_tags, strict=False):
            error_info = get_error_message_by_document("DocumentIndexerService", error, message)
            logger.error(f"Failed process=indexing error_detail={error_info}")
            self.reject_message(channel, delivery_tag)

    def _write_indexer_status(self, query: str, values: list[dict[str, Any]]) -> None:
        """Record the indexer outcome in MySQL without ever raising.

        Runs after messages are acked or rejected, so a MySQL error must not change
        the ack state or stop the consume loop.
        """
        try:
            self.db_conn.update_status(query, values)
        except Exception as e:
            logger.error(
                f"Failed to update indexer_status for batch_size={len(values)} "
                f"{get_general_error_message('DocumentIndexerService', e)}"
            )

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

        # Extract ht_ids now: batch.clear() below would lose them.
        # Docs without an "id" key are excluded from the status write and logged as a warning.
        # The ack/reject decision is unaffected — all docs are still acked or rejected with the batch.
        ht_ids: list[str] = [str(doc["id"]) for doc in batch if doc.get("id")]
        skipped = len(batch) - len(ht_ids)
        if skipped:
            logger.warning(f"Skipped {skipped} docs with no 'id' field from indexer status write.")

        start_time = time.time()

        success = True
        try:
            response = self.solr_api_full_text.index_documents(batch)
            logger.info(
                f"Success process=indexing {len(batch)} items."
                f"Operation status: {response.status_code} Time={time.time() - start_time:.10f} "
            )

            response.raise_for_status()

            # Acknowledge all messages in batch
            for delivery_tag in delivery_tags:
                self.positive_acknowledge(self.channel, delivery_tag)

        except Exception as e:
            logger.info(f"Failed process=indexing with error={e}")
            success = False
            error_msg = f"DocumentIndexerService_{type(e).__name__}: {e}"
            failed_messages = batch  # self.batch
            failed_messages_tags = delivery_tags.copy()
            # Requeue the full list of failed messages to the Dead Letter Queue
            self.requeue_failed_messages(failed_messages, failed_messages_tags, e, self.channel)
            self._write_indexer_status(
                FAILURE_UPDATE_STATUS,
                [
                    {
                        "indexer_status": ProcessingStatus.FAILED,
                        "processed_at": get_current_time(),
                        "error": error_msg,
                        "status": ProcessingStatus.FAILED,
                        "ht_id": ht_id,
                    }
                    for ht_id in ht_ids
                ],
            )
            logger.info(f"Wrote indexer_status=failed for {len(ht_ids)} items.")
        else:
            # In else, not try: messages are already acked, so a status-write error must
            # never reach the reject path above.
            self._write_indexer_status(
                SUCCESS_UPDATE_STATUS,
                [
                    {
                        "indexer_status": ProcessingStatus.COMPLETED,
                        "processed_at": get_current_time(),
                        "status": ProcessingStatus.COMPLETED,
                        "ht_id": ht_id,
                    }
                    for ht_id in ht_ids
                ],
            )
            logger.info(f"Wrote indexer_status=completed for {len(ht_ids)} items.")
        finally:
            batch.clear()
            delivery_tags.clear()
        return success


def start_service(
    solr_api_full_text: HTSolrAPI, queue_params: QueueParams, db_conn: HtMysql
) -> None:
    document_indexer_queue_service = DocumentIndexerQueueService(
        solr_api_full_text, db_conn, queue_params
    )
    logger.info(f"Starting Document Indexer Service with queue: {queue_params.queue_name}")
    # Start consuming messages from the queue
    document_indexer_queue_service.start_consuming()


def main() -> None:
    parser = argparse.ArgumentParser()

    init_args_obj = IndexerServiceArguments(parser)

    start_service(
        init_args_obj.solr_api_full_text,
        init_args_obj.queue_config.queue_params,
        init_args_obj.db_conn,
    )


if __name__ == "__main__":
    main()
