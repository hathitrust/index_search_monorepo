import argparse
import json
import time

from catalog_metadata.catalog_metadata import CatalogRecordMetadata, CatalogItemMetadata

from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_utils.ht_logger import get_ht_logger
from ht_utils.query_maker import make_query

logger = get_ht_logger(name=__name__)


def create_catalog_object_by_record_id(record: dict, catalog_record_metadata: CatalogRecordMetadata,
                                       results: list) -> list[CatalogItemMetadata]:
    """Receive a record and return a list of item, and their metadata
    :param record: dict with catalog record (retrieve from Solr)
    :param catalog_record_metadata: CatalogRecordMetadata object
    :param results: list of CatalogItemMetadata object
    """

    for item_id in record.get('ht_id'):
        results.append(CatalogRetrieverService.get_catalog_object(item_id, catalog_record_metadata))

    return results


def create_catalog_object_by_item_id(list_documents: list, record: dict,
                                     catalog_record_metadata: CatalogRecordMetadata, results: list) \
        -> list[CatalogItemMetadata]:
    """Receive a list of documents and a catalog record;
    Search for the item (ht_id) in the list and then;
    Create the CatalogMetadata object for each document in the list
    :param list_documents: list of ht_id
    :param record: dict with catalog record (retrieve from Solr)
    :param catalog_record_metadata: CatalogRecordMetadata object
    :param results: list of CatalogItemMetadata object
    """

    for item_id in record.get('ht_id'):
        if item_id in list_documents:
            results.append(CatalogRetrieverService.get_catalog_object(item_id, catalog_record_metadata))
    return results


class CatalogRetrieverService:
    """
    This class is used to retrieve the documents from the Catalog index
    It uses the HTSolrAPI to retrieve the documents from the Catalog index
    It accepts queries considering the field 'item' or 'record'. The default field is 'item'
    item is used to retrieve at ht_id level
    record is used to retrieve at id level, that means all the ht_id from a record
    """

    def __init__(self, catalog_api=None):

        self.catalog_api = HTSolrAPI(catalog_api)

    @staticmethod
    def get_catalog_object(item_id: str,
                           record_metadata: CatalogRecordMetadata) -> CatalogItemMetadata:

        catalog_item_metadata = CatalogItemMetadata(item_id, record_metadata)
        return catalog_item_metadata

    def count_documents(self, list_documents, start, rows, by_field: str = 'item'):

        """
        This method counts the number of documents to process having the list of documents
        :param list_documents: list of ids to process
        :param start: start index
        :param rows: number of rows to retrieve
        :param by_field: field to search by (item=ht_id or record=id)
        """
        # Build the query to retrieve the total of documents to process
        query = make_query(list_documents, by_field)

        try:
            response = self.catalog_api.get_documents(query=query, response_format="json", start=start, rows=rows)
            output = response.json()

            total_records = output.get("response").get("numFound")
            logger.info(f" Total of records {total_records}")

            return total_records if total_records else 0
        except Exception as e:
            logger.error(f"Error in getting documents from Solr {e}")
            raise e

    def retrieve_documents_from_solr(self, list_documents: list, start: int, rows: int, by_field: str = 'item'):

        """Function to retrieve documents from Solr
        :param list_documents: list of documents to retrieve from Solr index
        :param start: start index
        :param rows: number of rows to retrieve
        :param by_field: field to search by (item or record)
        """

        # try ... except block to catch any exception raised by the Solr connection
        try:
            response = self.catalog_api.get_documents(
                query=make_query(list_documents, by_field), start=start, rows=rows
            )

            output = json.loads(response.content.decode("utf-8"))

        except Exception as e:
            logger.error(f"Error in getting documents from Solr {e}")
            raise e

        return output

    def retrieve_documents(self, list_documents: list[str], start: int, rows: int, by_field: str = 'item') \
            -> list[CatalogItemMetadata]:

        """
        This method is used to retrieve the documents from the Catalog. For each document is generated a CatalogMedata
         object. The output of this method is a list of CatalogMetadata objects
        :param list_documents: list of documents to retrieve
        :param start: start index
        :param rows: number of rows to retrieve
        :param by_field: use this field to create the Solr query. item=ht_id and record=id
            Create the query, if only one item, so the query will be ht_id: item_id
         if more than one item, the query will be ht_id: (item_id1 OR item_id2 OR item_id3)
        """

        count_records = 0

        results = []

        # Query Solr to retrieve the documents
        output = self.retrieve_documents_from_solr(list_documents, start, rows, by_field)

        # If no documents are found, output.get("response").get("docs") is an empty list
        logger.info(f" {output.get('response').get('numFound')} documents found in Solr to process")
        for record in output.get("response").get("docs"):
            count_records = count_records + 1

            catalog_record_metadata = CatalogRecordMetadata(record)
            start_time = time.time()
            if by_field == 'item':
                # Validate query field = ht_id, list_documents could contain 1 or more items, but they probably are from
                # different records
                # Process a specific item of a record
                results = create_catalog_object_by_item_id(list_documents, record, catalog_record_metadata, results)
            # This is the most efficient way to retrieve the items from Catalog
            else:
                # Process all the items of a record
                results = create_catalog_object_by_record_id(record, catalog_record_metadata, results)

            logger.info(f"Time to retrieve document metadata {time.time() - start_time}")
        logger.info(f"Batch documents {count_records}")
        start += rows
        logger.info(f"Result length {len(results)}")
        return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--solr_url",
        help="Solr server URL",
        required=True,
        default="http://localhost:8983/solr/#/core-x/",
    )

    parser.add_argument("--query", help="Query used to retrieve documents", default='*:*'
                        )

    parser.add_argument("--output_file",
                        help="Path of the file to load the list of ht_id.",
                        required=False,
                        default="../items_list.txt"
                        )

    # Use case: Given a query, generate a list of ht_id from Catalog index
    args = parser.parse_args()

    solr_api_catalog = HTSolrAPI(url=args.solr_url)

    catalog_retrieval_service = CatalogRetrieverService(solr_api_catalog)

    count = 0
    # TODO Parallelize the process of retrieving documents from solr Catalog
    file_object = open(args.output_file, "w+")

    start = 0
    rows = 100

    # TODO Implement the use case that retrieve documents accept a query instead of a list of documents
    list_documents = []
    for result in catalog_retrieval_service.retrieve_documents(list_documents, start, rows, by_field='record'):
        item_id = result.ht_id
        logger.info(f"Item id: {item_id}")
        file_object.write(f"{item_id}\n")
        count = count + 1

    file_object.close()
    logger.info(count)


if __name__ == "__main__":
    main()
