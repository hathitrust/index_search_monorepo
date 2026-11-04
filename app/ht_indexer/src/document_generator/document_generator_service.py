import argparse
import sys
import time
from pathlib import Path
from typing import Any

from ht_document.ht_document import HtDocument
from ht_queue_service.queue_config import QueueParams
from ht_queue_service.queue_multiple_consumer import QueueMultipleConsumer
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_mysql import HtMysql
from ht_utils.ht_utils import get_error_message_by_document

from .full_text_document_generator import FullTextDocumentGenerator
from .generator_arguments import GeneratorServiceArguments

logger = get_ht_logger(name=__name__)


class DocumentGeneratorService(QueueMultipleConsumer):
    def __init__(
        self,
        db_conn: HtMysql,
        src_queue_params: QueueParams,
        tgt_queue_producer: QueueProducer | None,
        document_repository: str = "pairtree",
        tgt_local: bool = False,
    ):
        """
        This class is responsible to retrieve from the queue a message with metadata at item level and generate
        the full text search entry and publish the document in a queue

        :param db_conn: MySql connection
        :param src_queue_params: Queue parameters for retrieving messages from the queue
        :param tgt_queue_producer: Publishing messages to the queue
        :param tgt_local: Indicates if the document will be published in a queue or locally
        :param document_repository: Parameter to know if the plain text of the items is in the local or remote
        repository
        """

        super().__init__(src_queue_params)

        # Instantiate the document generator object
        self.document_generator = FullTextDocumentGenerator(db_conn)
        self.db_conn = db_conn

        self.document_repository = document_repository
        # Always set, even when tgt_local -- previously this attribute was only assigned in
        # the `not tgt_local` branch, so a tgt_local instance would raise AttributeError the
        # first time publish_document() ran instead of failing predictably.
        self.tgt_queue_producer = tgt_queue_producer if not tgt_local else None

    def generate_full_text_entry(
        self, item_id: str, record: dict[str, Any], document_repository: str
    ) -> dict[str, Any]:

        start_time = time.time()
        htid_logger = logger.bind(process="generate_full_text_entry", ht_id=item_id)
        htid_logger.info("Generating document")

        # Instantiate each document
        ht_document = HtDocument(document_id=item_id, document_repository=document_repository)

        # TODO: Temporal local for testing using a sample of files
        #  Checking if the file exist, otherwise go to the next
        if not Path(f"{ht_document.source_path}.zip").is_file():
            # The message is rejected because the file with the text of the document does not exist
            # then, entry dictionary could not be generated
            raise FileNotFoundError(
                f"The file of the ht_id={ht_document.document_id} on the path={ht_document.source_path}.zip not found"
            )
        htid_logger.info("Generating from file", file=ht_document.source_path + ".zip")
        try:
            entry = self.document_generator.make_full_text_search_document(ht_document, record)
        except Exception as e:
            raise Exception(
                f"Document htid={ht_document.document_id} could not be generated: Error - {e}"
            ) from e

        htid_logger.info("Finish", time=time.time() - start_time)

        return entry

    def publish_document(self, content: dict[str, Any] | None = None) -> None:
        """
        Publish the document in a queue
        """
        if content is None:
            raise ValueError("content is required")
        if self.tgt_queue_producer is None:
            raise RuntimeError("publish_document called on a tgt_local instance")
        message = content
        logger.info("Sending message to queue", ht_id=content.get("id"))
        self.tgt_queue_producer.publish_messages(message)

    def log_error_document_generator_service(
        self, e: Exception, document: dict[str, Any], delivery_tag: int
    ) -> None:
        """
        Log the error message when the document could not be generated and reject the message requeeing the message
        to the dead letter queue
        """
        error_info = get_error_message_by_document("DocumentGeneratorService", e, document)

        logger.error("document failed", ht_id=document.get("ht_id"), error=error_info)
        if self.channel is None:
            raise RuntimeError("Unable to establish a RabbitMQ channel")
        self.reject_message(self.channel, delivery_tag)

    def process_batch(self, batch: list[Any], delivery_tags: list[int]) -> bool:
        for message, tag in zip(batch, delivery_tags, strict=True):
            self.generate_document(message, tag)
        batch.clear()
        delivery_tags.clear()
        return True

    def generate_document(self, message: dict[str, Any], delivery_tag: int) -> None:

        item_id = message.get("ht_id")
        if item_id is None:
            # Fail early: without an ht_id there is nothing to generate.
            self.log_error_document_generator_service(
                ValueError("message is missing 'ht_id'"), message, delivery_tag
            )
            return

        # try to generate the full text entry dictionary, if it fails, the message is rejected
        try:
            full_text_document = self.generate_full_text_entry(
                item_id, message, self.document_repository
            )

            # try to publish the full text entry dictionary in the queue, if it fails, the message is
            # rejected
            self.publish_document(full_text_document)
            # Acknowledge the message to src_queue if the message is processed successfully and published in
            # the other queue
            if self.channel is None:
                raise RuntimeError("Unable to establish a RabbitMQ channel")
            self.positive_acknowledge(self.channel, delivery_tag)
        except Exception as e:
            self.log_error_document_generator_service(e, message, delivery_tag)


def main() -> None:
    parser = argparse.ArgumentParser()
    init_args_obj = GeneratorServiceArguments(parser)

    document_generator_service = DocumentGeneratorService(
        init_args_obj.db_conn,
        init_args_obj.src_queue_config.queue_params,
        init_args_obj.tgt_queue_producer,
        init_args_obj.document_repository,
        tgt_local=init_args_obj.tgt_local,
    )
    if not document_generator_service.start_consuming():
        # The error was already logged by start_consuming; exit non-zero so the orchestrator restarts us
        logger.error("[!] Exiting")
        sys.exit(1)


if __name__ == "__main__":
    main()
