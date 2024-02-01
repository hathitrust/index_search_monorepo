import os
import sys
import inspect

import argparse

from ht_utils.ht_logger import get_ht_logger
from ht_status_retriever_service import get_non_processed_ids

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

    def generate_full_text_entry(self, query, start, rows, all_items, document_repository, chunk=None):

        # TODO: Split the logic of retrieve_documents and generate_full_text_entry. The function that generates the entry
        # should receive the ht_id to process and their metadata.
        # The logic to retrieve from Catalog (all fields or only the first one) should be in the retrieve_documents function
        # Right now the logic is too complex because if I want to retrieve all the items of a record, then in the query I should I the id
        # but if I want to retrieve an specific item (ht_id), then I should use the ht_id field in the query
        # This is not intuitive and it is not clear
        # An issue of the current implementation is that we are processing the first element of the record and not the
        # ht_id passed as a parameter

        for results in self.retrieve_documents(query, start, rows):
            for record in results:
                """
                if all_items:
                    # Process all the records of a Catalog
                    total_items = len(record.get("ht_id"))
                else:
                    # Process the first item of the Catalog record
                    total_items = 1
                """
                for i in range(0, len(record.get("ht_id"))):
                    current_ht_id = record.get("ht_id")[i]
                    if current_ht_id in chunk:
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

                            yield entry, ht_document.file_name, ht_document.namespace, item_id
                        else:
                            logger.info(f"{ht_document.document_id} does not exist")
                            continue
                    else:
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

    # Path to the folder where the documents are stored. This parameter is useful for runing the script locally
    parser.add_argument(
        "--document_local_path",
        help="Path of the folder where the documents (.xml file to index) are stored.",
        required=False,
        default=None
    )

    parser.add_argument(
        "--list_ids_path",
        help="Path of the TXT files with the list of id to generate",
        required=False,
        default=None
    )

    args = parser.parse_args()

    document_generator = DocumentGenerator(db_conn)

    document_indexer_service = FullTextSearchRetrieverService(
        solr_api_catalog, document_generator
    )

    document_local_folder = "indexing_data"
    document_local_path = DOCUMENT_LOCAL_PATH

    # Create the directory to load the xml files if it does not exit

    try:
        if args.document_local_path:
            document_local_path = os.path.abspath(args.document_local_path)
        os.makedirs(os.path.join(document_local_path, document_local_folder))
    except FileExistsError:
        pass

    count = 0
    query = args.query
    start = 0
    rows = 100

    status_file = os.path.join(parentdir, "document_retriever_status.txt")

    if args.list_ids_path:
        # If a document with the list of id to process is received as a parameter, then create batch of queries
        with open(args.list_ids_path) as f:
            list_ids = f.read().splitlines()

            ids2process, processed_ids = get_non_processed_ids(status_file, list_ids)

            logger.info(f"Total of items to process {len(ids2process)}")

            tmp_file_status = open(os.path.join(document_local_path, "document_retriever_status.txt"), "w+")
            for doc in processed_ids:
                tmp_file_status.write(doc + "\n")
            tmp_file_status.close()

            while ids2process:
                chunk, ids2process = ids2process[:100], ids2process[100:]
                values = "\" OR \"".join(chunk)
                values = '"'.join(("", values, ""))
                query = f"ht_id:({values})"

                for (
                        entry,
                        file_name,
                        namespace,
                        item_id
                ) in document_indexer_service.generate_full_text_entry(
                    query,
                    start,
                    rows,
                    all_items=args.all_items,
                    document_repository=args.document_repository,
                    chunk=chunk
                ):
                    count = count + 1
                    solr_str = create_solr_string(entry)
                    logger.info(f"Creating XML file to index")
                    with open(
                            f"/{os.path.join(document_local_path, document_local_folder)}/{namespace}{file_name}_solr_full_text.xml",
                            "w",
                    ) as f:
                        f.write(solr_str)

                    with open(os.path.join(document_local_path, 'document_retriever_status.txt'), "a+") as file:
                        file.write(item_id + "\n")

                    logger.info(count)

    else:
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
                    f"/{os.path.join(document_local_path, document_local_folder)}/{namespace}{file_name}_solr_full_text.xml",
                    "w",
            ) as f:
                f.write(solr_str)

            logger.info(count)


if __name__ == "__main__":
    main()
