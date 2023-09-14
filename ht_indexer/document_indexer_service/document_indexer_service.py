# Read from a folder, index documents to solr and delete the content of the sercer

import logging
from time import sleep
import argparse
import os
import glob

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
        logging.info("Cleaning up .xml and .Zip files")

        for id_name in list_ids:
            # zip file
            list_documents = glob.glob(f"{document_path}/{id_name}")
            for file in list_documents:
                logging.info(f"Deleting file {file}")
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
    document_local_path = os.path.abspath("/tmp/indexing_data/")

    while True:
        # Get the files for indexing
        xml_files = [
            file
            for file in os.listdir(document_local_path)
            if file.lower().endswith(".xml")
        ]

        # Split the list of files in batch
        if xml_files:
            while xml_files:
                chunk, xml_files = xml_files[:CHUNK_SIZE], xml_files[CHUNK_SIZE:]

                logging.info(f"Indexing documents: {chunk}")
                response = document_indexer_service.indexing_documents(
                    document_local_path
                )

                if response.status_code == 200:
                    DocumentIndexerService.clean_up_folder(document_local_path, chunk)

        logging.info(f"Processing ended, sleeping for 5 minutes")
        sleep(300)

    """
    for entry in document_indexer_service.generate_full_text_entry():

        solr_str = create_solr_string(entry)

        list_ids.append(obj_id)
        with open(
                f"/tmp/{obj_id}_solr_full_text.xml",
                "w",
        ) as f:
            f.write(solr_str)

        if len(list_ids) >= 10:
            logging.info(f"Indexing documents: {list_ids}")
            response = document_retrieval_service.indexing_documents(
                document_local_path
            )

            if response.status_code == 200:
                DocumentRetrievalService.clean_up_folder(document_local_path, list_ids)

            list_ids = []
    """

    """
    if len(list_ids) > 0:
        logging.info(f"Indexing documents: {list_ids}")
        response = document_retrieval_service.indexing_documents(document_local_path)

        if response.status_code == 200:
            DocumentRetrievalService.clean_up_folder(document_local_path, list_ids)

    logging.info(f"Indexed {count} records")
    """


if __name__ == "__main__":
    main()
