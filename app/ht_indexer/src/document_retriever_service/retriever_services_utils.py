import json

from catalog_metadata.catalog_metadata import CatalogItemMetadata, CatalogRecordMetadata
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)
class RetrieverServicesUtils:
    """
    A utility class for the Document Retriever Service.
    """

    @staticmethod
    def publish_document(queue_producer_conn: QueueProducer, content: dict = None):
        """
        Publish the document in a queue
        :param queue_producer: QueueProducer object
        :param content: dict with the content of the message
        """
        message = content
        entry_data = json.dumps(message)
        entry_size = len(entry_data.encode('utf-8'))  # Convert to bytes and get length
        logger.info(f"Sending message with id {content.get('ht_id')} and Size={entry_size} bytes to queue {queue_producer_conn.queue_name}")
        queue_producer_conn.publish_messages(message)

    @staticmethod
    def get_catalog_object(item_id: str,
                           record_metadata: CatalogRecordMetadata) -> CatalogItemMetadata:

        catalog_item_metadata = CatalogItemMetadata(item_id, record_metadata)
        return catalog_item_metadata

    @staticmethod
    def extract_ids_from_documents(list_documents, by_field):
        """
        Prepare the list of ids to be processed
        :param list_documents: list of documents to process
        :param by_field: field to search by (item=ht_id or record=id)
        :return: list of ids to be processed
        """

        if by_field == 'record':
            list_documents = [record['record_id'] for record in list_documents]

        if by_field == 'item':
            list_documents = [record['ht_id'] for record in list_documents]

        return list_documents

    @staticmethod
    def create_catalog_object_by_record_id(record: dict, catalog_record_metadata: CatalogRecordMetadata) -> list[
        CatalogItemMetadata]:
        """Receive a record and return a list of item, and their metadata
        :param record: dict with catalog record (retrieve from Solr)
        :param catalog_record_metadata: CatalogRecordMetadata object
        """

        results = []
        for item_id in record.get('ht_id'):
            results.append(RetrieverServicesUtils.get_catalog_object(item_id, catalog_record_metadata))

        return results

    @staticmethod
    def create_catalog_object_by_item_id(list_documents: list, record: dict,
                                         catalog_record_metadata: CatalogRecordMetadata) \
            -> list[CatalogItemMetadata]:
        """Receive a list of documents and a catalog record;
        Search for the item (ht_id) in the list and then;
        Create the CatalogMetadata object for each document in the list
        :param list_documents: list of ht_id
        :param record: dict with catalog record (retrieve from Solr)
        :param catalog_record_metadata: CatalogRecordMetadata object
        """
        results = []
        for item_id in record.get('ht_id'):
            if item_id in list_documents:
                results.append(RetrieverServicesUtils.get_catalog_object(item_id, catalog_record_metadata))
        return results

