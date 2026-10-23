from typing import Any

from catalog_metadata.catalog_metadata import CatalogItemMetadata, CatalogRecordMetadata
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class RetrieverServicesUtils:
    """
    A utility class for the Document Retriever Service.
    """

    @staticmethod
    def publish_document(queue_producer_conn: QueueProducer, content: dict[str, Any]) -> None:
        """
        Publish the document in a queue
        :param queue_producer_conn: QueueProducer object
        :param content: dict with the content of the message
        """
        logger.info(
            f"Sending message with htid={content.get('ht_id')} "
            f"to queue {queue_producer_conn.queue_manager.queue_name}"
        )
        queue_producer_conn.publish_messages(content)

    @staticmethod
    def get_catalog_object(
        item_id: str, record_metadata: CatalogRecordMetadata
    ) -> CatalogItemMetadata:

        catalog_item_metadata = CatalogItemMetadata(item_id, record_metadata)
        return catalog_item_metadata

    @staticmethod
    def extract_hathitrust_ids(list_documents: list[dict[str, Any]]) -> list[str]:
        """
        Prepare the list of ids to be processed
        :param list_documents: list of records
        :return: list of ids to be processed
        """

        return [record["ht_id"] for record in list_documents]

    @staticmethod
    def extract_catalog_record_id(list_documents: list[dict[str, Any]]) -> list[str]:
        """
        Prepare the list of ids to be processed
        :param list_documents: list of records
        :return: list of ids to be processed
        """

        return [record["record_id"] for record in list_documents]
