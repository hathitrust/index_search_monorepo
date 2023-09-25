import logging
from typing import Text
from utils.ht_pairtree import download_document_file
from document_generator.indexer_config import (
    DOCUMENT_LOCAL_PATH,
    SDR_DIR,
    TRANSLATE_TABLE,
)

from pypairtree import pairtree


class HtDocument:
    """
    This class manage the basic information we need to process a document
    * ht_id
    * make sure the document have .zip and mets file
    * Download the fields and load their path
    * Rename the files of the document if the id has the following pattern: uc2.ark:/13960/t4mk66f1d
    """

    def __init__(self, document_id: Text = None):
        self.document_id = document_id

        self.namespace = HtDocument.get_namespace(document_id)
        self.obj_id = HtDocument.get_object_id(document_id)

        # If there is special characters in the document_id, the file will be save in the local
        # environment with a different name
        self.file_name = pairtree.sanitizeString(self.obj_id)  # self.set_file_name()

        self.source_path = self.get_document_source_path()

        self.target_path = f"{DOCUMENT_LOCAL_PATH}{self.file_name}"

        # Download document .zip and .mets.xml file
        # TODO: Check if file exist
        download_document_file(
            source_path=self.source_path, target_path=self.target_path, extension="zip"
        )

        # Download document .zip and .mets.xml file
        # TODO: Check if file exist
        download_document_file(
            source_path=self.source_path,
            target_path=self.target_path,
            extension="mets.xml",
        )

    @staticmethod
    def get_namespace(document_id):
        try:
            namespace = document_id.split(".")[0]
            return namespace
        except ValueError as e:
            logging.error(f"Review the document id {document_id} {e}")

    @staticmethod
    def get_object_id(document_id):
        try:
            obj_id = document_id.split(".")[1:]
            if len(obj_id) > 1:  # It means the document_id contains more than one point
                return '.'.join(obj_id)
            return ''.join(obj_id)
        except ValueError as e:
            logging.error(f"Review the document id {document_id} {e}")

    def get_document_source_path(self):
        """
        If the ht_id contains special characters e.g. uc2.ark:/13960/t4mk66f1d, python can not use this
        name to read and write the zip file, then this method uses pairtree python package to replace
        special characters
        :return:
        """

        # Use the file name to get the pairtree path
        doc_path = pairtree.get_pair_path(self.file_name)

        # Escape special characters from the file of the path and the object name
        doc_translated_path = doc_path.translate(TRANSLATE_TABLE)
        sanitized_obj_id_translated = self.file_name.translate(TRANSLATE_TABLE)

        source_path = f"{SDR_DIR}/obj/{self.namespace}/pairtree_root{doc_translated_path}/{sanitized_obj_id_translated}"

        return source_path
