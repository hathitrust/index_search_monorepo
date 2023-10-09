# from document_retrieval_service.document_retrieval_service import DocumentRetrievalService
import json
import logging
import argparse

from document_retriever_service.document_retriever_service import (
    DocumentRetrieverService,
)
from ht_indexer_api.ht_indexer_api import HTSolrAPI


class CatalogRetrieverService(DocumentRetrieverService):
    def __init__(self, catalogApi=None):
        super().__init__()

        self.catalogApi = catalogApi

    def retrieve_documents(self, query, start, rows):
        response = self.catalogApi.get_documents(query=query, start=start, rows=rows)
        output = response.json()

        try:
            total_records = output.get("response").get("numFound")
            logging.info(total_records)
        except Exception as e:
            logging.error(f"Solr index {self.catalogApi} seems empty {e}")
            exit()
        count_records = 0
        while count_records < total_records:
            results = []
            response = self.catalogApi.get_documents(
                query=query, start=start, rows=rows
            )

            output = json.loads(response.content.decode("utf-8"))

            for record in output.get("response").get("docs"):
                count_records = count_records + 1
                results.append(record)

            logging.info(f"Batch documents {count_records}")
            start += rows
            logging.info(f"Result lenght {len(results)}")
            yield results

    def retrieve_list_ht_ids(self, query, start, rows, all_items: bool = False):
        total_htid = 0
        for results in self.retrieve_documents(query, start, rows):
            for record in results:
                if all_items:
                    for item_id in record.get("ht_id"):
                        total_htid = total_htid + 1
                        logging.info(f"Processing document {item_id}")
                        yield item_id
                else:
                    try:
                        item_id = record.get("ht_id")[0]
                    except Exception as e:
                        logging.error(
                            f"The record {record.get('id')} does not have items."
                        )
                        continue
                    total_htid = total_htid + 1
                    logging.info(f"Processing document {item_id}")
                    yield item_id
                    continue

            logging.info(f"Total of items (ht_id) {total_htid}")

    """
    def make_full_text_search_document(self):

        query = "*:*"
        start = 0
        rows = 100

        total_htid = 0
        for results in self.retrieve_documents(query, start, rows):

            for record in results:
                for item_id in record.get("ht_id"):
                    total_htid = total_htid + 1
                    logging.info(f"Processing document {item_id}")
                    yield item_id
            logging.info(f"Total of items (ht_id) {total_htid}")
    """


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--solr_url",
        help="Solr server URL",
        required=True,
        default="http://localhost:8983/solr/#/core-x/",
    )
    parser.add_argument(
        "--all_items",
        help="If store, you will obtain all the items of record, otherwise you will retrieve only the first item",
        action="store_true",
        default=False,
    )

    args = parser.parse_args()

    solr_api_catalog = HTSolrAPI(url=args.solr_url)

    catalog_retrieval_service = CatalogRetrieverService(solr_api_catalog)

    count = 0
    # TODO How can I paralelize the process of retrieving documents from solr Catalog?
    # Print ids
    file_object = open("../items_list.txt", "w+")

    query = "*:*"
    start = 0
    rows = 100

    for ht_id in catalog_retrieval_service.retrieve_list_ht_ids(
        query, start, rows, all_items=args.all_items
    ):
        count = count + 1
        # list_ids.append(ht_id)
        logging.info(f"Item id: {ht_id}")
        file_object.write(f"{ht_id}\n")

    file_object.close()
    logging.info(count)


if __name__ == "__main__":
    main()
