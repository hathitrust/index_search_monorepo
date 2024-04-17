# Read from a folder, index documents to solr and delete the content of the sercer

import argparse
import inspect
import os
import sys

from ht_queue_service.queue_consumer import QueueConsumer
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
        for message in self.queue_consumer.consume_message():

            try:
                response = self.storage_document(json_object=message)
                logger.info(f"Index operation status: {response.status_code}")

            except Exception as e:
                logger.info(f"Something went wrong with Solr {e}")


def main():
    parser = argparse.ArgumentParser()

    from document_indexer_service.indexer_arguments import IndexerServiceArguments
    init_args_obj = IndexerServiceArguments(parser)

    document_indexer_queue_service = DocumentIndexerQueueService(init_args_obj.solr_api_full_text,
                                                                 init_args_obj.queue_consumer)

    document_indexer_queue_service.indexer_service()


if __name__ == "__main__":
    main()
