import argparse
import json
import time

from catalog_metadata.catalog_metadata import CatalogRecordMetadata, CatalogItemMetadata

from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_utils.ht_logger import get_ht_logger
from ht_utils.query_maker import make_query

logger = get_ht_logger(name=__name__)


def get_specific_item_id(query):
    # Process a specific item of a record
    try:
        item_id = query.split(':')[1]
    except Exception as e:
        logger.error(f"Query {query} does not have a valid format {e}")
        exit()
    return [item_id]


def create_catalog_object_by_record_id(record, catalog_record_metadata, results):
    for item_id in record.get('ht_id'):  # Append list of CatalogMetadata object
        results.append(CatalogRetrieverService.get_catalog_object(item_id, catalog_record_metadata))

    return results


def create_catalog_object_by_item_id(list_documents, record, catalog_record_metadata, results):
    # TODO: To optimize the process, we could remove the item included in results from the list_documents
    for item_id in record.get('ht_id'):
        if item_id in list_documents:
            results.append(CatalogRetrieverService.get_catalog_object(item_id, catalog_record_metadata))
    return results


class CatalogRetrieverService:
    def __init__(self, catalog_api=None):

        self.catalog_api = HTSolrAPI(catalog_api)

    @staticmethod
    def get_catalog_object(item_id: str,
                           record_metadata: CatalogRecordMetadata) -> CatalogItemMetadata:

        catalog_item_metadata = CatalogItemMetadata(item_id, record_metadata)
        return catalog_item_metadata

    def count_documents(self, list_documents, start, rows, by_field: str = 'item'):

        """
        This method is used to load the list of ht_id from the Catalog index
        """
        # Build query to know the total of documents to process
        query = make_query(list_documents, by_field)

        response = self.catalog_api.get_documents(query=query, start=start, rows=rows)
        output = response.json()
        try:
            total_records = output.get("response").get("numFound")
            logger.info(f" Total of records {total_records}")
        except Exception as e:
            logger.error(f"Solr index {self.catalog_api} seems empty {e}")
            exit()
        return total_records

    def retrieve_documents(self, list_documents: list[str], start: int, rows: int, by_field: str = 'item'):

        """
        Input: list of ht_id

        by_field: 'item' or 'record'

        Create the query, if only one item, so the query will be ht_id: item_id
        if more than one item, the query will be ht_id: (item_id1 OR item_id2 OR item_id3)
        This method is used to retrieve the documents from the Catalog, then it will be used to return instances
        of a CatalogMetadata

        """

        count_records = 0

        results = []

        response = self.catalog_api.get_documents(
            query=make_query(list_documents, by_field), start=start, rows=rows
        )

        output = json.loads(response.content.decode("utf-8"))

        # TODO: Add a check to verify if the response is empty

        for record in output.get("response").get("docs"):
            count_records = count_records + 1

            catalog_record_metadata = CatalogRecordMetadata(record)
            start_time = time.time()
            if by_field == 'item':
                # Validate query field = ht_id, list_documents could contain 1 or more items but they probably are form
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
        logger.info(f"Result lenght {len(results)}")
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

    for result in catalog_retrieval_service.retrieve_documents(start, rows):
        for record in result:
            item_id = record.ht_id
            logger.info(f"Item id: {item_id}")
            file_object.write(f"{item_id}\n")
            count = count + 1

    file_object.close()
    logger.info(count)


if __name__ == "__main__":
    main()
