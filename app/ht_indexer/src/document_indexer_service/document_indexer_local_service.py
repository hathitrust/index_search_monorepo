# Read from a folder, index documents to solr and delete the content of the server

import argparse
import glob
import os
from time import sleep

import requests
from ht_indexer_api.ht_indexer_api import (
    DEFAULT_READ_TIMEOUT_SECONDS,
    HTSolrAPI,
    positive_seconds,
)
from ht_utils.ht_env_config import HtEnvConfig
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

DOCUMENT_LOCAL_PATH = "/tmp/indexing_data/"
SLEEP_SECONDS = 3


class DocumentIndexerLocalService:
    def __init__(self, solr_api_full_text: HTSolrAPI):
        self.solr_api_full_text = solr_api_full_text

    def indexing_documents(self, path: str, list_documents: list[str]) -> requests.Response:
        # Call API
        response = self.solr_api_full_text.index_documents_by_file(
            path, list_documents=list_documents
        )
        return response

    @staticmethod
    def _log_failure(file: str, error: OSError) -> None:
        # The file stays in the folder; it is tried again on the next pass
        # RequestException is an OSError too, and only it can carry a response from Solr
        response = (
            error.response if isinstance(error, requests.exceptions.RequestException) else None
        )
        logger.error(
            "local_indexing_failed",
            file=file,
            status_code=response.status_code if response is not None else None,
            error=str(error),
        )

    @staticmethod
    def clean_up_folder(document_path: str, list_ids: list[str]) -> None:
        logger.info("Cleaning up .xml and .zip files")

        for id_name in list_ids:
            # zip file
            list_documents = glob.glob(f"{document_path}/{id_name}")
            for file in list_documents:
                logger.info(f"Deleting file {file}")
                os.remove(file)

    def indexer_service(self, document_local_path: str | None = None) -> None:

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
                # One file at a time: a file that Solr accepts is cleaned up at once, and a file
                # that Solr rejects stays in the folder without holding back the others.
                for file in json_files:
                    try:
                        response = self.indexing_documents(
                            document_local_path, list_documents=[file]
                        )
                        logger.info(f"Index operation status: {response.status_code}")
                        self.clean_up_folder(document_local_path, [file])
                    except requests.exceptions.HTTPError as error:
                        # Solr answered with an error for this file: go on with the next one
                        self._log_failure(file, error)
                        continue
                    except requests.exceptions.RequestException as error:
                        # Solr did not answer: the other files would fail the same way
                        self._log_failure(file, error)
                        break
                    except OSError as error:
                        # The file could not be read or deleted: go on with the next one.
                        # This must come after the two handlers above, because RequestException
                        # is an OSError too.
                        self._log_failure(file, error)
                        continue

            except Exception as e:
                # Most likely the folder does not exist yet, but any other error ends up here too
                logger.warning(
                    "local_indexing_pass_failed",
                    path=document_local_path,
                    error=str(e),
                )
                sleep(SLEEP_SECONDS)  # Wait until the folder is created

            logger.info(f"Processing ended, sleeping for {SLEEP_SECONDS} seconds")
            sleep(SLEEP_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser()

    # Path to the folder where the documents are stored. This parameter is useful for running the script locally
    parser.add_argument(
        "--document_local_path",
        help="Path of the folder where the documents are stored.",
        required=False,
        default=None,
    )

    parser.add_argument(
        "--solr_timeout",
        type=positive_seconds,
        default=DEFAULT_READ_TIMEOUT_SECONDS,
        help="Seconds to wait for Solr to send data before a request fails (default: "
        f"{DEFAULT_READ_TIMEOUT_SECONDS:g}). Requests with commit=true can stay silent while Solr "
        "commits, so raise it for big files.",
    )

    args = parser.parse_args()

    solr_api_full_text = HTSolrAPI(HtEnvConfig().solr_full_text_rw, read_timeout=args.solr_timeout)

    document_indexer_service = DocumentIndexerLocalService(solr_api_full_text)

    document_indexer_service.indexer_service(args.document_local_path)


if __name__ == "__main__":
    main()
