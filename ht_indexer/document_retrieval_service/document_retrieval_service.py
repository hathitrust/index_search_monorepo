import argparse
import json
import logging

from ht_indexer_api.ht_indexer_api import HTSolrAPI
from document_generator.document_generator import DocumentGenerator
from utils.ht_mysql import create_mysql_conn
from utils.text_processor import create_solr_string
from pathlib import Path
from typing import Dict


class DocumentRetrievalService:
    def __init__(self, catalogApi=None):
        self.catalogApi = catalogApi

    def get_record_metadata(self, query: str = None) -> Dict:
        """
        API call to query Catalog Solr index
        :param query: input query
        :return dictionary with the API result

        """
        response = self.catalogApi.get_documents(query)

        return {
            "status": response.status_code,
            "description": response.headers,
            "content": json.loads(response.content.decode("utf-8")),
        }

    def retrieve_documents(self, db_conn):
        query = "*:*"
        response = self.catalogApi.get_documents(query)
        result = json.loads(response.content.decode("utf-8"))

        document_generator = DocumentGenerator(db_conn)

        for doc in result.get("response").get("docs"):
            for doc_id in doc.get("ht_id"):
                logging.info(f"Processing document {doc_id}")
                entry = document_generator.make_document(doc_id, doc)

                yield entry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--solr_url",
        help="",
        required=True,
        default="http://localhost:8983/solr/#/core-x/",
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

    solr_api = HTSolrAPI(url=args.solr_url)

    document_retrieval_service = DocumentRetrievalService(solr_api)

    count = 0
    for entry in document_retrieval_service.retrieve_documents(db_conn):
        count = count + 1
        solr_str = create_solr_string(entry)

        obj_id = entry.get('id').split(".")[1]

        with open(
                f"{Path(__file__).parents[1]}/ht_indexer_api/data/add/{obj_id}_solr_full_text.xml",
                "w",
        ) as f:
            f.write(solr_str)

        if count == 5:
            logging.info(f"Processed {count} documents")

            break


if __name__ == "__main__":
    main()
