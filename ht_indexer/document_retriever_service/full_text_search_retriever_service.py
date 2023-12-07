import os
import sys
import inspect

import argparse

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

from document_generator.document_generator import DocumentGenerator
from catalog_retriever_service import CatalogRetrieverService

from ht_indexer_api.ht_indexer_api import HTSolrAPI

from ht_utils.ht_mysql import create_mysql_conn
from ht_utils.text_processor import create_solr_string
from document_generator.indexer_config import DOCUMENT_LOCAL_PATH
from ht_document.ht_document import HtDocument


class FullTextSearchRetrieverService(CatalogRetrieverService):
    def __init__(self, catalogApi=None, document_generator=None):
        super().__init__(catalogApi=catalogApi)

        self.document_generator = document_generator

    def generate_full_text_entry(self, query, start, rows, all_items, document_repository):
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
                    logger.info(f"Item ID {item_id}")

                    logger.info(f"Processing document {item_id}")

                    # Instantiate each document
                    ht_document = HtDocument(document_id=item_id, document_repository=document_repository)

                    logger.info(f"Checking path {ht_document.source_path}")

                    # TODO: Temporal local for testing using a sample of files
                    #  Checking if the file exist, otherwise go to the next
                    if os.path.isfile(f"{ht_document.source_path}.zip"):

                        logger.info(f"Processing item {ht_document.document_id}")

                        try:
                            entry = self.document_generator.make_full_text_search_document(
                                ht_document, record
                            )
                            # yield entry
                        except Exception as e:
                            logger.error(f"Document {item_id} failed {e}")
                            continue

                        yield entry, ht_document.file_name, ht_document.namespace
                    else:
                        logger.info(f"{ht_document.document_id} does not exist")
                        continue


def main():
    parser = argparse.ArgumentParser()

    # Catalog Solr server
    try:
        solr_url = os.environ["SOLR_URL"]
    except KeyError:
        logger.error("Error: `SOLR_URL` environment variable required")
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
        logger.error("Error: `MYSQL_PASS` environment variable required")
        sys.exit(1)

    db_conn = create_mysql_conn(
        host=mysql_host,
        user=mysql_user,
        password=mysql_pass,
        database=os.environ.get("MYSQL_DATABASE", "ht"),
    )
    logger.info("Access by default to `ht` Mysql database")

    # By default, only the first item of each record is process
    # If ALL_ITEMS=True, then all the items per record will be processed
    parser.add_argument(
        "--all_items",
        help="If store, you will obtain all the items of record, otherwise you will retrieve only the first item",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--query", help="Query used to retrieve documents", default="*:*"
    )
    parser.add_argument(
        "--document_repository", help="Could be pairtree or local", default="local"
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
        document_repository=args.document_repository
    ):
        count = count + 1
        solr_str = create_solr_string(entry)
        logger.info(f"Creating XML file to index")
        with open(
                f"/{os.path.join(DOCUMENT_LOCAL_PATH, document_local_path)}/{namespace}{file_name}_solr_full_text.xml",
                "w",
        ) as f:
            f.write(solr_str)

        logger.info(count)


if __name__ == "__main__":
    main()
