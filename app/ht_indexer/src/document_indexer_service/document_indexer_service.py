import argparse
import sys
import time
from typing import Any

import requests
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_queue_service.queue_config import QueueParams
from ht_queue_service.queue_multiple_consumer import QueueMultipleConsumer
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import get_error_message_by_document, get_queue_message_id
from pika.adapters.blocking_connection import BlockingChannel

from .failure_classifier import (
    UNAVAILABLE_STATUS_CODES,
    FailureKind,
    classify_failure,
    failure_type,
)
from .indexer_arguments import IndexerServiceArguments

logger = get_ht_logger(name=__name__)

# Fields whose value is free text. They are always quoted and, by convention, come last.
_FREE_TEXT_FIELDS = {"error", "error_detail"}


class DocumentIndexerQueueService(QueueMultipleConsumer):
    # Wait after a batch that put messages back: 1s, 2s, 4s... up to the cap.
    BACKOFF_BASE_SECONDS = 1.0
    BACKOFF_MAX_SECONDS = 60.0
    # A failed request logs at most this many ids. --batch_size can be up to 65535, and a line that
    # long may be dropped by the log system. `docs` always has the full count.
    MAX_LOGGED_IDS = 100

    def __init__(self, solr_api_full_text: HTSolrAPI, queue_params: QueueParams):
        """Initialize the Document Indexer Queue Service.
        :param solr_api_full_text: The Solr API client for full-text indexing
        :param queue_params: The object with the queue parameters
        """
        # Call the parent class constructor that initializes the connection to the queue
        super().__init__(queue_params)
        self.solr_api_full_text = solr_api_full_text
        # How many times a message may be put back after Solr answered its own request with a 5xx
        self.max_retries = queue_params.max_retries
        # Failed attempts per message, kept in memory only: it starts again from zero on restart.
        self.retry_attempts: dict[str, int] = {}
        # Messages put back during the current batch, and consecutive batches that put some back
        self.retried_in_batch = 0
        self.consecutive_retry_batches = 0
        self.logger = logger.bind()

    @staticmethod
    def _message_key(message: dict[str, Any]) -> str:
        """Identify a message across redeliveries. Messages are Solr documents, so the id is in
        `id` (get_queue_message_id also checks `ht_id`). A message without an id is never retried:
        Solr rejects it with a 400, so it goes straight to the dead-letter queue.
        """
        return get_queue_message_id(message)

    def _exceeded_max_retries(self, message: dict[str, Any]) -> bool:
        """Record one more failed attempt for the message; True once it has used up its retries."""
        key = self._message_key(message)
        self.retry_attempts[key] = self.retry_attempts.get(key, 0) + 1
        return self.retry_attempts[key] > self.max_retries

    def _ack(self, message: dict[str, Any], delivery_tag: int, channel: BlockingChannel) -> None:
        self.retry_attempts.pop(self._message_key(message), None)
        self.positive_acknowledge(channel, delivery_tag)

    def _backoff(self) -> None:
        """Wait before reading the next batch if this one put messages back, so a down Solr (or a
        message that keeps failing) is not hit in a tight loop. A clean batch resets the wait.
        """
        if self.retried_in_batch == 0:
            self.consecutive_retry_batches = 0
            return
        self.consecutive_retry_batches += 1
        # The exponent is capped so a very long outage cannot overflow the float
        delay = min(
            self.BACKOFF_BASE_SECONDS * 2 ** min(self.consecutive_retry_batches - 1, 16),
            self.BACKOFF_MAX_SECONDS,
        )
        self.logger.info(
            "indexing_backoff",
            messages_put_back=self.retried_in_batch,
            consecutive_batches=self.consecutive_retry_batches,
            wait_seconds=delay,
        )
        # ASSUMPTION: heartbeat is 0 for the indexer (heartbeat in indexer_config.yml), so this long
        # blocking sleep cannot make the broker drop the connection. pika only answers heartbeats
        # while it is doing I/O. If the heartbeat is ever enabled (> 0), revisit this: sleep in
        # shorter steps, or with the connection's own sleep() so heartbeats keep being processed.
        time.sleep(delay)

    def _index(self, documents: list[dict[str, Any]]) -> None:
        """Send documents to Solr in one request. Raises if the request or the response fails."""
        start_time = time.time()
        response = self.solr_api_full_text.index_documents(documents)
        response.raise_for_status()

        for i in documents:
            self.logger.info("document_indexed", ht_id=get_queue_message_id(i))

        self.logger.info(
            "batch_indexed",
            item_count=len(documents),
            http_status=response.status_code,
            seconds=time.time() - start_time,
        )

    def _log_solr_failure(
        self, scope: str, documents: list[dict[str, Any]], error: Exception
    ) -> None:
        """Log a failed request to Solr with the ids of the messages that were in it (the first
        MAX_LOGGED_IDS), so a timeout or an outage can be traced to the items it affected.
        """
        self.logger.error(
            "solr_request_failed",
            scope=scope,
            docs=len(documents),
            ht_ids=[
                get_queue_message_id(document) for document in documents[: self.MAX_LOGGED_IDS]
            ],
            failure_kind=classify_failure(error).value,
            failure_type=failure_type(error),
            error=str(error),
        )

    def _attempt_label(self, message: dict[str, Any]) -> str:
        return f"{self.retry_attempts[self._message_key(message)]}/{self.max_retries}"

    def _retry(
        self,
        message: dict[str, Any],
        delivery_tag: int,
        error: Exception,
        channel: BlockingChannel,
        counted: bool = False,
    ) -> None:
        """Leave a message on the original queue to be tried again; the message is not at fault.
        :param counted: True if this attempt counts towards max_retries (see _exceeded_max_retries)
        """
        fields: dict[str, object] = {
            "ht_id": get_queue_message_id(message),
            "failure_kind": classify_failure(error).value,
        }
        if counted:
            fields["attempt"] = self._attempt_label(message)
        self.logger.warning("message_retried", **fields, error=str(error))
        self.retried_in_batch += 1
        self.retry_message(channel, delivery_tag)

    def _dead_letter(
        self,
        message: dict[str, Any],
        delivery_tag: int,
        error: Exception,
        channel: BlockingChannel,
        reason: str = "bad_document",
    ) -> None:
        """Send a message that can never be indexed to the Dead Letter Queue.
        :param reason: bad_document, or retries_exhausted if it kept failing with a 5xx
        """
        self.retry_attempts.pop(self._message_key(message), None)
        error_info = get_error_message_by_document("DocumentIndexerService", error, message)
        self.logger.error(
            "message_dead_lettered",
            ht_id=get_queue_message_id(message),
            reason=reason,
            queue=self.queue_manager.dead_letter_queue_name,
            failure_kind=classify_failure(error).value,
            error_detail=error_info,
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
        self.retried_in_batch = 0

        try:
            self._index(batch)
        except Exception as e:
            self._log_solr_failure("batch", batch, e)
            all_acked = self._handle_failed_batch(batch, delivery_tags, e, channel)
        else:
            for message, delivery_tag in zip(batch, delivery_tags, strict=True):
                self._ack(message, delivery_tag, channel)
            all_acked = True

        batch.clear()
        delivery_tags.clear()
        self._backoff()
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
                self._log_solr_failure("document", [message], doc_error)
                if classify_failure(doc_error) is FailureKind.PERMANENT:
                    self._dead_letter(message, delivery_tag, doc_error, channel)
                elif _solr_cannot_be_used(doc_error):
                    # Not the message's fault, so this attempt is not counted against it.
                    self._retry(message, delivery_tag, doc_error, channel)
                    blocked_by = doc_error
                elif self._exceeded_max_retries(message):
                    # Solr keeps answering this one document with a 5xx: treat it as a poison message.
                    self._dead_letter(
                        message, delivery_tag, doc_error, channel, reason="retries_exhausted"
                    )
                else:
                    self._retry(message, delivery_tag, doc_error, channel, counted=True)
            else:
                self._ack(message, delivery_tag, channel)
        return all_acked


def _solr_cannot_be_used(error: Exception) -> bool:
    """True when retrying a single document is pointless: Solr is unreachable (no HTTP answer at
    all), says it is unavailable (429/502/503/504), or is refusing our credentials. Any other 5xx
    answer is not included, since one bad document can cause it.
    """
    kind = classify_failure(error)
    if kind is FailureKind.CONFIG_ERROR:
        return True
    if kind is not FailureKind.TRANSIENT:
        return False
    if not isinstance(error, requests.exceptions.HTTPError):
        return True
    return error.response is not None and error.response.status_code in UNAVAILABLE_STATUS_CODES


def start_service(solr_api_full_text: HTSolrAPI, queue_params: QueueParams) -> bool:
    document_indexer_queue_service = DocumentIndexerQueueService(solr_api_full_text, queue_params)
    logger.info(f"Starting Document Indexer Service with queue: {queue_params.queue_name}")
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
