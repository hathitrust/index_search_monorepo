import os
import sys
import inspect

import argparse
import glob

from utils.ht_logger import HTLogger

logger = HTLogger(name=__file__)

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

from document_generator.document_generator import DocumentGenerator
from catalog_retriever_service import CatalogRetrieverService

from ht_indexer_api.ht_indexer_api import HTSolrAPI

from utils.ht_mysql import create_mysql_conn
from utils.text_processor import create_solr_string
from document_generator.indexer_config import DOCUMENT_LOCAL_PATH
from ht_document.ht_document import HtDocument


class FullTextSearchRetrieverService(CatalogRetrieverService):
    def __init__(self, catalogApi=None, document_generator=None):
        super().__init__(catalogApi=catalogApi)

        self.document_generator = document_generator

    def generate_full_text_entry(self, query, start, rows, all_items, document_folder):
        for results in self.retrieve_documents(query, start, rows):
            for record in results:
                if all_items:
                    # Process all the records of a Catalog
                    total_items = len(record.get("ht_id"))
                else:
                    # Process the first item of the Catalog record
                    total_items = 1

                for i in range(0, total_items):
                    item_id = record.get("ht_id")[i]

                    logger.info(f"Processing document {item_id}")

                    # Instantiate each document
                    ht_document = HtDocument(
                        document_id=item_id, document_folder=document_folder
                    )

                    # obj_id = record.get("id").split(".")[1]
                    logger.info(f"Processing item {ht_document.document_id}")

                    try:
                        entry = self.document_generator.make_full_text_search_document(
                            ht_document, record
                        )
                        # yield entry
                    except Exception as e:
                        logger.info(f"Document {item_id} failed {e}")
                        continue

                    yield entry, ht_document.file_name, ht_document.namespace

    @staticmethod
    def clean_up_folder(document_path, list_ids):
        logger.info("Cleaning up .xml and .Zip files")

        for id_name in list_ids:
            # zip file
            list_documents = glob.glob(f"{document_path}/{id_name}.zip")
            for file in list_documents:
                logger.info(f"Deleting file {file}")
                os.remove(file)
            list_documents = glob.glob(f"{document_path}/{id_name}.mets.xml")
            for file in list_documents:
                logger.info(f"Deleting file {file}")
                os.remove(file)


def main():
    parser = argparse.ArgumentParser()

    # parser.add_argument("--mysql_database", help="MySql database", required=True, default='ht')

    # Catalog Solr server
    try:
        solr_url = os.environ["SOLR_URL"]
    except KeyError:
        logger.error("Error: `API_KEY` environment variable required")
        sys.exit(1)

    solr_api_catalog = HTSolrAPI(url=solr_url)

    # MySql connection
    try:
        mysql_host = os.environ["MYSQL_HOST"]
    except KeyError:
        logger.error("Error: `MYSQL_HOST` environment variable required")
        sys.exit(1)

    try:
        mysql_user = os.environ["MYSQL_USER"]
    except KeyError:
        logger.error("Error: `MYSQL_USER` environment variable required")
        sys.exit(1)

    try:
        mysql_pass = os.environ["MYSQL_PASS"]
    except KeyError:
        logger.error("Error: `MYSQL_USER` environment variable required")
        sys.exit(1)

    db_conn = create_mysql_conn(
        host=mysql_host,
        user=mysql_user,
        password=mysql_pass,
        database=os.environ.get("MYSQL_DATABASE", "ht"),
    )
    logger.info("Access by default to `ht` Mysql database")

    parser.add_argument(
        "--all_items",
        help="If store, you will obtain all the items of record, otherwise you will retrieve only the first item",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--clean_up",
        help="If store, you will delete all the input file",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--query", help="Query used to retrieve documents", default="*:*"
    )

    parser.add_argument(
        "--document_folder", help="Path to read files from filesystem", default=None
    )

    args = parser.parse_args()

    document_generator = DocumentGenerator(db_conn)

    document_indexer_service = FullTextSearchRetrieverService(
        solr_api_catalog, document_generator
    )

    document_local_path = "indexing_data"

    # Create the directory to load the xml files if it does not exit
    try:
        os.makedirs(os.path.join(DOCUMENT_LOCAL_PATH, document_local_path))
    except FileExistsError:
        pass

    count = 0
    query = args.query
    start = 0
    rows = 50

    for (
        entry,
        file_name,
        namespace,
    ) in document_indexer_service.generate_full_text_entry(
        query,
        start,
        rows,
        all_items=args.all_items,
        document_folder=args.document_folder,
    ):
        count = count + 1
        solr_str = create_solr_string(entry)

        with open(
            f"/{os.path.join(DOCUMENT_LOCAL_PATH, document_local_path)}/{namespace}{file_name}_solr_full_text.xml",
            "w",
        ) as f:
            f.write(solr_str)

        logger.info(count)
        # Clean up
        if args.clean_up:
            FullTextSearchRetrieverService.clean_up_folder(
                DOCUMENT_LOCAL_PATH, [file_name]
            )


if __name__ == "__main__":
    main()
