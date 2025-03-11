import os
from typing import Text

from pypairtree import pairtree

from ht_utils.ht_logger import get_ht_logger
from ht_indexer_config import (
    DOCUMENT_LOCAL_PATH,
    LOCAL_DOCUMENT_FOLDER
)

logger = get_ht_logger(name=__name__)


class HtDocument:
    """
    The class manages the basic information we need to process a document
    * ht_id
    * make sure the document have .zip and mets file
    * Download the fields and load their path
    * Rename the files of the document if the id has the following pattern: uc2.ark:/13960/t4mk66f1d
    """

    def __init__(self, document_id: Text = None, document_repository: Text = 'local'):  # pairtree or local
        # TODO: I should create two classes one a document retrieved from pairtree-based repo
        #  and other one a document retrieve for any folder, so pass the attribute , source_file: Text = None
        # Right now this class only retrieve documents from a pairtree-based repo

        self.document_id = document_id

        self.namespace = HtDocument.get_namespace(document_id)
        self.obj_id = HtDocument.get_object_id(document_id)

        # If there are special characters in the document_id, the file will be load in the local
        # environment with a different name
        self.file_name = pairtree.sanitizeString(self.obj_id)

        # By default path files are in /sdr1/obj
        if document_repository == 'pairtree':
            self.source_path = f"{os.environ.get('SDR_DIR')}/{self.namespace}/pairtree_root{self.get_document_pairtree_path()}"  # /sdr1/obj/
        else:
            # A sample_data will be in the same folder of the repository
            self.source_path = f"{LOCAL_DOCUMENT_FOLDER}/{self.file_name}"

        self.target_path = f"{DOCUMENT_LOCAL_PATH}{self.file_name}"

    @staticmethod
    def get_namespace(document_id):
        try:
            namespace = document_id.split(".")[0]
            return namespace
        except ValueError as e:
            logger.error(f"Review the document id {document_id} {e}")

    @staticmethod
    def get_object_id(document_id):
        try:
            obj_id = document_id.split(".")[1:]
            if len(obj_id) > 1:  # It means the document_id contains more than one point
                return ".".join(obj_id)
            return "".join(obj_id)
        except ValueError as e:
            raise ValueError(f"Review the document id {document_id} {e}")

    def get_document_pairtree_path(self):
        """
        If the ht_id contains special characters e.g. uc2.ark:/13960/t4mk66f1d, python can not use this
        name to read and write the zip file, then this method uses pairtree python package to replace
        special characters
        :return:
        """

        # Use the file name to get the pairtree path
        doc_pairtree_path = pairtree.toPairTreePath(self.obj_id)
        doc_path = f"/{doc_pairtree_path}{pairtree.sanitizeString(self.obj_id)}/{self.file_name}"
        return doc_path
