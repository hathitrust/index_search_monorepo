# from document_retrieval_service.document_retrieval_service import DocumentRetrievalService
import json
import logging
import argparse

from document_retrieval_service import DocumentRetrievalService
from ht_indexer_api.ht_indexer_api import HTSolrAPI


class CatalogRetrievalService(DocumentRetrievalService):

    def __init__(self, catalogApi=None):

        super().__init__()

        self.catalogApi = catalogApi

    def retrieve_documents(self, query, start, rows):
        query = "*:*"
        start = 0
        rows = 100

        results = []

        response = self.catalogApi.get_documents(query=query, start=start,
                                                 rows=rows)
        output = response.json()

        total_records = output.get("response").get("numFound")
        count_records = 0
        while count_records < total_records:

            response = self.catalogApi.get_documents(query=query, start=start,
                                                     rows=rows)

            output = json.loads(response.content.decode("utf-8"))

            for record in output.get("response").get("docs"):
                count_records = count_records + 1
                results.append(record)

            logging.info(f"Batch documents {count_records}")
            start += rows
            yield results

    def retrieve_list_ht_ids(self):

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
        help="",
        required=True,
        default="http://localhost:8983/solr/#/core-x/",
    )

    # parser.add_argument(
    #    "--solr_indexing_api",
    #    help="",
    #    required=True,
    #    default="http://localhost:8082/solrIndexing/#/core-x/",
    # )

    # parser.add_argument(
    #    "--mysql_host", help="Host to connect to MySql server", required=True
    # )
    # parser.add_argument(
    #    "--mysql_user", help="User to connect to MySql server", required=True
    # )
    # parser.add_argument(
    #    "--mysql_pass", help="Password to connect to MySql server", required=True
    # )
    # parser.add_argument("--mysql_database", help="MySql database", required=True)

    args = parser.parse_args()

    # db_conn = create_mysql_conn(
    #    host=args.mysql_host,
    #    user=args.mysql_user,
    #    password=args.mysql_pass,
    #    database=args.mysql_database,
    # )

    solr_api_catalog = HTSolrAPI(url=args.solr_url)
    # solr_api_full_text = HTSolrAPI(url=args.solr_indexing_api)

    catalog_retrieval_service = CatalogRetrievalService(
        solr_api_catalog
    )

    count = 0
    list_ids = []
    # TODO How can I paralelize the process of retrieving documents from solr Catalog?
    # Print ids
    for ht_id in catalog_retrieval_service.retrieve_list_ht_ids():
        list_ids.append(ht_id)
    logging.info(f"Total of elements {len(list_ids)}")

    unique_htids = list(set(list_ids))
    logging.info(f"Total of unique elements {len(unique_htids)}")

    file_object = open("items_list.txt", "w+")
    for ht_id in unique_htids:
        file_object.write(f"{ht_id}\n")

    file_object.close()
    logging.info(count)


if __name__ == "__main__":
    main()
