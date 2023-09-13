from document_retrieval_service.catalog_retrieval_service import CatalogRetrievalService
from document_generator.document_generator import DocumentGenerator
from ht_indexer_api.ht_indexer_api import HTSolrAPI

from utils.ht_mysql import create_mysql_conn
from utils.text_processor import create_solr_string
from pathlib import Path
from typing import Dict

import logging
import argparse


class FullTextSearchRetrievalService(CatalogRetrievalService):

    def __init__(self, catalogApi=None, document_generator=None):
        super().__init__(catalogApi=catalogApi)

        self.document_generator = document_generator

    def generate_full_text_entry(self, query, start, rows):

        for results in self.retrieve_documents(query, start, rows):
            for record in results:
                for item_id in record.get("ht_id"):
                    logging.info(f"Processing document {item_id}")

                    obj_id = record.get("id").split(".")[1]
                    logging.info(f"Processing item {obj_id}")

                    try:
                        entry = self.document_generator.make_document(item_id, record)
                        yield entry
                    except Exception as e:
                        logging.info(f"Document {item_id} failed {e}")
                        continue

                    yield entry


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--solr_url",
        help="",
        required=True,
        default="http://localhost:8082/solrIndexing/#/core-x/",
    )

    parser.add_argument(
        "--mysql_host", help="Host to connect to MySql server", required=True
    )
    parser.add_argument(
        "--mysql_user", help="User to connect to MySql server", required=True
    )
    parser.add_argument(
        "--mysql_pass", help="Password to connect to MySql server", required=True
    )
    parser.add_argument("--mysql_database", help="MySql database", required=True)

    args = parser.parse_args()

    db_conn = create_mysql_conn(
        host=args.mysql_host,
        user=args.mysql_user,
        password=args.mysql_pass,
        database=args.mysql_database,
    )

    solr_api_catalog = HTSolrAPI(url=args.solr_url)

    document_generator = DocumentGenerator(db_conn)

    document_indexer_service = FullTextSearchRetrievalService(solr_api_catalog,
                                                              document_generator
                                                              )

    document_local_path = "indexing_data"
    list_ids = []
    for entry in document_indexer_service.generate_full_text_entry():
        solr_str = create_solr_string(entry)
        obj_id = entry.get("id").split(".")[1]

        list_ids.append(obj_id)
        with open(
                f"/{document_local_path}/{obj_id}_solr_full_text.xml",
                "w",
        ) as f:
            f.write(solr_str)


if __name__ == "__main__":
    main()
