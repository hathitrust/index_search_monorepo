# Read from a folder, index documents to solr and delete the content of the server

import argparse
import glob
import inspect
import os
import sys
from time import sleep

from ht_indexer_api.ht_indexer_api import HTSolrAPI
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

CHUNK_SIZE = 500
DOCUMENT_LOCAL_PATH = "/tmp/indexing_data/"


class DocumentIndexerLocalService:
    def __init__(self, solr_api_full_text: HTSolrAPI = None):
        self.solr_api_full_text = solr_api_full_text

    def indexing_documents(self, path, list_documents=None):
        # Call API
        response = self.solr_api_full_text.index_documents(path, list_documents=list_documents)
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

    def indexer_service(self, document_local_path: str = None):

        while True:
            try:
                if document_local_path:
                    document_local_path = os.path.abspath(document_local_path)
                else:
                    document_local_path = os.path.abspath(DOCUMENT_LOCAL_PATH)

                # Get the files for indexing
                json_files = [
                    file
                    for file in os.listdir(document_local_path)
                    if file.lower().endswith(".json")
                ]

                logger.info(f"Indexing {len(json_files)} documents.")
                # Split the list of files in batch
                if json_files:
                    while json_files:
                        chunk, json_files = json_files[:CHUNK_SIZE], json_files[CHUNK_SIZE:]

                        logger.info(f"Indexing documents: {chunk}")
                        response = self.indexing_documents(
                            document_local_path, list_documents=chunk
                        )
                        logger.info(f"Index operation status: {response.status_code}")
                        if response.status_code == 200:
                            self.clean_up_folder(
                                document_local_path, chunk
                            )

            except Exception as e:
                logger.info(f"{document_local_path} does not exit {e}")
                sleep(3)  # Wait until the folder is created

            logger.info("Processing ended, sleeping for 5 minutes")
            sleep(3)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--solr_indexing_api",
        help="",
        required=True,
        default="http://solr-lss-dev:8983/solr/#/core-x/",
    )

    # Path to the folder where the documents are stored. This parameter is useful for running the script locally
    parser.add_argument(
        "--document_local_path",
        help="Path of the folder where the documents are stored.",
        required=False,
        default=None
    )

    args = parser.parse_args()

    solr_api_full_text = HTSolrAPI(url=args.solr_indexing_api)

    document_indexer_service = DocumentIndexerLocalService(solr_api_full_text)

    document_indexer_service.indexer_service(args.document_local_path)


if __name__ == "__main__":
    main()
