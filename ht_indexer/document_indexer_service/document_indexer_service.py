# Read from a folder, index documents to solr and delete the content of the sercer

import argparse
import inspect
import os
import sys
import json
import time

from ht_queue_service.queue_consumer import QueueConsumer, positive_acknowledge
from ht_utils import ht_utils
from ht_utils.ht_logger import get_ht_logger
from ht_indexer_api.ht_indexer_api import HTSolrAPI

logger = get_ht_logger(name=__name__)

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)


class DocumentIndexerQueueService:
    def __init__(self, solr_api_full_text: HTSolrAPI,
                 queue_consumer: QueueConsumer):
        self.solr_api_full_text = solr_api_full_text
        self.queue_consumer = queue_consumer

    def storage_document(self, json_object: dict = None):

        # Call API
        response = self.solr_api_full_text.index_document(content_type="application/json", xml_data=json_object)
        return response

    def indexer_service(self):
        # Get ten messages and break out
        for method_frame, properties, body in self.queue_consumer.consume_message():
            start_time = time.time()
            message = json.loads(body.decode('utf-8'))

            # Use to get the size of the entry dictionary
            entry_data = json.dumps(message)
            entry_size = len(entry_data.encode('utf-8'))  # Convert to bytes and get length
            logger.info(
                f"Serialized JSON process=indexing ht_id={message.get('id')} Size={entry_size} bytes")

            try:
                logger.info(f"Retrieving the item {message.get('id')} from {self.queue_consumer.queue_name}")
                response = self.storage_document(json_object=message)
                logger.info(
                    f"Success process=indexing the item ht_id={message.get('id')}. Operation status: {response.status_code} Time={time.time() - start_time:.10f}")
                positive_acknowledge(self.queue_consumer.conn.ht_channel, method_frame.delivery_tag)
            except Exception as e:
                error_info = ht_utils.get_error_message_by_document("IndexerService",
                                                                    e, message)
                logger.error(f"Document={message.get('ht_id')} failed {error_info} Time={time.time() - start_time:.10f}")
                self.queue_consumer.reject_message(self.queue_consumer.conn.ht_channel, method_frame.delivery_tag)


def main():
    parser = argparse.ArgumentParser()

    from document_indexer_service.indexer_arguments import IndexerServiceArguments
    init_args_obj = IndexerServiceArguments(parser)

    document_indexer_queue_service = DocumentIndexerQueueService(init_args_obj.solr_api_full_text,
                                                                 init_args_obj.queue_consumer)

    document_indexer_queue_service.indexer_service()


if __name__ == "__main__":
    main()
