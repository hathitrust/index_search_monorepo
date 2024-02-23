import argparse
import json

from catalog_metadata.catalog_metadata import CatalogRecordMetadata, CatalogItemMetadata

from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class CatalogRetrieverService:
    def __init__(self, catalog_api=None):

        self.catalog_api = catalog_api

    @staticmethod
    def get_catalog_object(record: dict, item_id: str,
                           record_metadata: CatalogRecordMetadata) -> CatalogItemMetadata:

        catalog_item_metadata = CatalogItemMetadata(record, item_id, record_metadata)
        return catalog_item_metadata

    def retrieve_documents(self, query, start, rows):

        """
        This method is used to retrieve the documents from the Catalog, then it will be used to return instances
        of a CatalogMetadata
        """

        response = self.catalog_api.get_documents(query=query, start=start, rows=rows)
        output = response.json()

        try:
            total_records = output.get("response").get("numFound")
            logger.info(total_records)
        except Exception as e:
            logger.error(f"Solr index {self.catalog_api} seems empty {e}")
            exit()
        count_records = 0
        while count_records < total_records:
            results = []
            response = self.catalog_api.get_documents(
                query=query, start=start, rows=rows
            )

            output = json.loads(response.content.decode("utf-8"))

            # TODO: Add a check to verify if the response is empty

            for record in output.get("response").get("docs"):
                count_records = count_records + 1

                catalog_record_metadata = CatalogRecordMetadata(record)
                if 'ht_id' in query:
                    # Process a specific item of a record
                    try:
                        item_id = query.split(':')[1]
                    except Exception as e:
                        logger.error(f"Query {query} does not have a valid format {e}")
                        exit()
                    results.append(CatalogRetrieverService.get_catalog_object(record, item_id, catalog_record_metadata))
                # This is the most efficient way to retrieve the items from Catalog
                else:
                    # Process all the items of a record
                    for item_id in record.get('ht_id'):  # Append list of CatalogMetadata object
                        results.append(CatalogRetrieverService.get_catalog_object(record, item_id,
                                                                                  catalog_record_metadata))

            logger.info(f"Batch documents {count_records}")
            start += rows
            logger.info(f"Result lenght {len(results)}")
            yield results


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

    for result in catalog_retrieval_service.retrieve_documents(args.query, start, rows):
        for record in result:
            item_id = record.ht_id
            logger.info(f"Item id: {item_id}")
            file_object.write(f"{item_id}\n")
            count = count + 1

    file_object.close()
    logger.info(count)


if __name__ == "__main__":
    main()
