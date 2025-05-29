import argparse
import json
import time
from pathlib import Path

from full_text_document_generator import FullTextDocumentGenerator
from generator_arguments import GeneratorServiceArguments
from ht_document.ht_document import HtDocument
from ht_queue_service.queue_consumer import QueueConsumer, positive_acknowledge
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import get_error_message_by_document, get_general_error_message

logger = get_ht_logger(name=__name__)

class DocumentGeneratorService:
    def __init__(self, db_conn, src_queue_consumer: QueueConsumer,
                 tgt_queue_producer: QueueProducer | None,
                 document_repository: str = None,
                 not_required_tgt_queue: bool = False
                 ):

        """
        This class is responsible to retrieve from the queue a message with metadata at item level and generate
        the full text search entry and publish the document in a queue

        :param db_conn: MySql connection
        :param src_queue_consumer: Retrieving messages from the queue
        :param tgt_queue_producer: Publishing messages to the queue
        :param not_required_tgt_queue: Indicates if the document will be published in a queue or locally
        :param document_repository: Parameter to know if the plain text of the items is in the local or remote
        repository
        """

        # Instantiate the document generator object
        self.document_generator = FullTextDocumentGenerator(db_conn)

        self.src_queue_consumer = src_queue_consumer
        self.document_repository = document_repository
        if not not_required_tgt_queue:
            self.tgt_queue_producer = tgt_queue_producer

    def generate_full_text_entry(self, item_id: str, record: dict, document_repository: str):

        start_time = time.time()
        logger.info(f"Generating document {item_id}")

        # Instantiate each document
        ht_document = HtDocument(document_id=item_id, document_repository=document_repository)

        # TODO: Temporal local for testing using a sample of files
        #  Checking if the file exist, otherwise go to the next
        if not Path(f"{ht_document.source_path}.zip").is_file():
            # The message is rejected because the file with the text of the document does not exist
            # then, entry dictionary could not be generated
            raise FileNotFoundError(f"The file of the ht_id={ht_document.document_id} on the path={ht_document.source_path}.zip not found")
        logger.info(f"Processing item {ht_document.document_id} using {ht_document.source_path}.zip")
        try:
            entry = self.document_generator.make_full_text_search_document(ht_document, record)
        except Exception as e:
            raise Exception(f"Document {ht_document.document_id} could not be generated: Error - {e}") from e

        # Use to get the size of the entry dictionary
        entry_data = json.dumps(entry)
        entry_size = len(entry_data.encode('utf-8'))  # Convert to bytes and get length
        logger.info(f"Time to generate process=full-text_document ht_id={ht_document.document_id} "
                    f"Time={time.time() - start_time:.10f} Size={entry_size} bytes")

        return entry

    def publish_document(self, content: dict = None):
        """
        Publish the document in a queue
        """
        message = content
        logger.info(f"Sending message to queue {content.get('id')}")
        self.tgt_queue_producer.publish_messages(message)

    def log_error_document_generator_service(self, e, document, delivery_tag):
        """
        Log the error message when the document could not be generated and reject the message requeeing the message
        to the dead letter queue
        """
        error_info = get_error_message_by_document("DocumentGeneratorService",
                                                                     e, document)

        logger.error(f"Document {document.get('ht_id')} failed {error_info}")
        self.src_queue_consumer.reject_message(self.src_queue_consumer.conn.ht_channel,
                                               delivery_tag)

    def consume_messages(self):
        try:
            for method_frame, _properties, body in self.src_queue_consumer.consume_message():
                message = json.loads(body.decode('utf-8'))
                self.generate_document(message, method_frame.delivery_tag)
        except Exception as e:
            logger.error(f"There is something wrong with the queue connection: "
                         f"{get_general_error_message('DocumentGeneratorService', e)}")

    def generate_document(self, message: dict, delivery_tag: int):

        item_id = message.get("ht_id")

        # try to generate the full text entry dictionary, if it fails, the message is rejected
        try:
            full_text_document = self.generate_full_text_entry(item_id, message, self.document_repository)

            # try to publish the full text entry dictionary in the queue, if it fails, the message is
            # rejected
            self.publish_document(full_text_document)
            # Acknowledge the message to src_queue if the message is processed successfully and published in
            # the other queue
            positive_acknowledge(self.src_queue_consumer.conn.ht_channel,
                                 delivery_tag)
        except Exception as e:
            self.log_error_document_generator_service(e, message, delivery_tag)


def main():
    parser = argparse.ArgumentParser()
    init_args_obj = GeneratorServiceArguments(parser)

    document_generator_service = DocumentGeneratorService(init_args_obj.db_conn,
                                                          init_args_obj.src_queue_consumer,
                                                          init_args_obj.tgt_queue_producer,
                                                          init_args_obj.document_repository,
                                                          not_required_tgt_queue=init_args_obj.not_required_tgt_queue
                                                          )
    document_generator_service.consume_messages()


if __name__ == "__main__":
    main()
