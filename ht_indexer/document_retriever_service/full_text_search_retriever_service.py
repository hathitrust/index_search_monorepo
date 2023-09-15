import os
import sys
import inspect

import logging
import argparse
import glob

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

from document_generator.document_generator import DocumentGenerator
from catalog_retrieval_service import CatalogRetrievalService

from ht_indexer_api.ht_indexer_api import HTSolrAPI

from utils.ht_mysql import create_mysql_conn
from utils.text_processor import create_solr_string


class FullTextSearchRetrievalService(CatalogRetrievalService):

    def __init__(self, catalogApi=None, document_generator=None):
        super().__init__(catalogApi=catalogApi)

        self.document_generator = document_generator

    def generate_full_text_entry(self, query, start, rows, all_items):

        for results in self.retrieve_documents(query, start, rows):
            for record in results:
                if all_items:
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
                else:
                    item_id = record.get("ht_id")[0]
                    logging.info(f"Processing document {item_id}")

                    try:
                        entry = self.document_generator.make_document(item_id, record)
                        yield entry
                    except Exception as e:
                        logging.info(f"Document {item_id} failed {e}")
                        continue
                    yield entry
                    continue

    @staticmethod
    def clean_up_folder(document_path, list_ids):
        logging.info("Cleaning up .xml and .Zip files")

        for id_name in list_ids:
            # zip file
            list_documents = glob.glob(f"{document_path}/{id_name}.zip")
            for file in list_documents:
                logging.info(f"Deleting file {file}")
                os.remove(file)
            list_documents = glob.glob(f"{document_path}/{id_name}.mets.xml")
            for file in list_documents:
                logging.info(f"Deleting file {file}")
                os.remove(file)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--solr_url",
        help="",
        required=True,
        default="http://localhost:8082/solrIndexing/#/core-x/",
    )

    parser.add_argument(
        "--all_items",
        help="If store, you will obtain all the items of record, otherwise you will retrieve only the first item",
        action="store_true",
        default=False,
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

    # Create the directory to load the xml files if it does not exit
    try:
        os.makedirs(os.path.join("/tmp", document_local_path))
    except FileExistsError:
        pass

    count = 0
    query = "*:*"
    start = 0
    rows = 50

    logging.info(args.mysql_host)
    logging.info(args.mysql_user)
    logging.info(args.mysql_pass)
    logging.info(args.mysql_database)
    for i in [1, 2, 3, 4, 5, 6]:
        logging.info(i)

    """
    for entry in document_indexer_service.generate_full_text_entry(query, start, rows, all_items=args.all_items):
        count = count + 1
        solr_str = create_solr_string(entry)
        obj_id = entry.get("id").split(".")[1]

        with open(
                f"/{os.path.join('/tmp', document_local_path)}/{obj_id}_solr_full_text.xml",
                "w",
        ) as f:
            f.write(solr_str)

        # Clean up
        FullTextSearchRetrievalService.clean_up_folder("/tmp", [obj_id])
        if count > 150:
            break
    """


if __name__ == "__main__":
    main()
