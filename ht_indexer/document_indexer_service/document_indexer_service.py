# Read from a folder, index documents to solr and delete the content of the sercer

from time import sleep
import argparse
import os
import glob
import inspect
import sys

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

CHUNK_SIZE = 500
DOCUMENT_LOCAL_PATH = "/tmp/indexing_data/"

from ht_indexer_api.ht_indexer_api import HTSolrAPI


class DocumentIndexerService:
    def __init__(self, solr_api_full_text=None):
        self.solr_api_full_text = solr_api_full_text

    def indexing_documents(self, path, list_documents=None):
        # Call API
        response = self.solr_api_full_text.index_document(path, list_documents=list_documents)
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
        default="http://solr-lss-dev:8983/solr/#/core-x/",
    )

    # Path to the folder where the documents are stored. This parameter is useful for runing the script locally
    parser.add_argument(
        "--document_local_path",
        help="Path of the folder where the documents are stored.",
        required=False,
        default=None
    )

    args = parser.parse_args()

    solr_api_full_text = HTSolrAPI(url=args.solr_indexing_api)

    document_indexer_service = DocumentIndexerService(solr_api_full_text)

    while True:
        try:
            if args.document_local_path:
                document_local_path = os.path.abspath(args.document_local_path)
            else:
                document_local_path = os.path.abspath(DOCUMENT_LOCAL_PATH)

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
                        document_local_path, list_documents=chunk
                    )
                    logger.info(f"Index operation status: {response.status_code}")
                    if response.status_code == 200:
                        DocumentIndexerService.clean_up_folder(
                            document_local_path, chunk
                        )

        except Exception as e:
            logger.info(f"{document_local_path} does not exit {e}")
            sleep(30)  # Wait until the folder is created

        logger.info(f"Processing ended, sleeping for 5 minutes")
        sleep(30)


if __name__ == "__main__":
    main()
