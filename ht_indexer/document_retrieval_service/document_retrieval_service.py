import argparse
import json
import logging

from ht_indexer_api.ht_indexer_api import HTSolrAPI
from document_generator.document_generator import DocumentGenerator
from utils.ht_mysql import create_mysql_conn
from utils.text_processor import create_solr_string
from pathlib import Path
from typing import Dict
import os
import glob


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
        "--solr_indexing_api",
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
    solr_api_full_text = HTSolrAPI(url=args.solr_indexing_api)

    document_retrieval_service = DocumentRetrievalService(solr_api_catalog)

    count = 0

    # TODO How can I paralelize the process of retrieving documents from solr Catalog?
    for entry in document_retrieval_service.retrieve_documents(db_conn):
        count = count + 1
        solr_str = create_solr_string(entry)

        obj_id = entry.get('id').split(".")[1]

        with open(
                f"/tmp/{obj_id}_solr_full_text.xml",
                "w",
        ) as f:
            f.write(solr_str)

        if count > 5:
            logging.info(f"Processed {count} documents")

            # Call API
            document_path = "/tmp"
            response = solr_api_full_text.index_document(document_path)
            # TODO To clean up we should check what are the fields to remove in the current thread
            if response.status_code == 200:
                logging.info("Cleaning up")
                list_documents = glob.glob(f"{document_path}/*.xml")
                for file in list_documents:
                    logging.info(f"Deleting file {file}")
                    os.remove(file)
            count = 0
        if count == 0:
            break


if __name__ == "__main__":
    main()
