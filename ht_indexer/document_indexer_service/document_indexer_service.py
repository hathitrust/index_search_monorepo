# Read from a folder, index documents to solr and delete the content of the sercer

import logging
from time import sleep
import argparse
import os
import glob
import inspect
import sys

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

logging.basicConfig(
    filename="full_text_search_indexer_service.log",
    filemode="w",
    format="%(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

CHUNK_SIZE = 50

from ht_indexer_api.ht_indexer_api import HTSolrAPI


class DocumentIndexerService:
    def __init__(self, solr_api_full_text=None):
        self.solr_api_full_text = solr_api_full_text

    def indexing_documents(self, path):
        # Call API
        response = self.solr_api_full_text.index_document(path)
        return response

    @staticmethod
    def clean_up_folder(document_path, list_ids):
        logger.info("Cleaning up .xml and .zip files")

        for id_name in list_ids:
            # zip file
            list_documents = glob.glob(f"{document_path}/{id_name}")
            for file in list_documents:
                logger.info(f"Deleting file {file}")
                os.remove(file)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--solr_indexing_api",
        help="",
        required=True,
        default="http://localhost:8082/solrIndexing/#/core-x/",
    )

    args = parser.parse_args()

    solr_api_full_text = HTSolrAPI(url=args.solr_indexing_api)

    document_indexer_service = DocumentIndexerService(solr_api_full_text)

    while True:
        try:
            document_local_path = os.path.abspath("/tmp/indexing_data/")

            # Get the files for indexing
            xml_files = [
                file
                for file in os.listdir(document_local_path)
                if file.lower().endswith(".xml")
            ]

            logger.info(f"Indexing {len(xml_files)} documents.")
            # Split the list of files in batch
            if xml_files:
                while xml_files:
                    chunk, xml_files = xml_files[:CHUNK_SIZE], xml_files[CHUNK_SIZE:]

                    logger.info(f"Indexing documents: {chunk}")
                    response = document_indexer_service.indexing_documents(
                        document_local_path
                    )
                    logger.info(f"Index opperation status: {response.status_code}")
                    if response.status_code == 200:
                        DocumentIndexerService.clean_up_folder(
                            document_local_path, chunk
                        )

        except Exception as e:
            logger.info(f"/tmp/indexing_data/ does not exit {e}")
            sleep(30)  # Wait until the folder is created

        logger.info(f"Processing ended, sleeping for 5 minutes")
        sleep(30)


if __name__ == "__main__":
    main()
