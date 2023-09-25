import pytest
import os
import inspect
import sys

from document_indexer_service.document_indexer_service import DocumentIndexerService


class TestFullTextRetrieverService:
    def test_retrieve_xml_fields_from_directory(self):
        document_local_path = os.path.abspath("/tmp/indexing_data/")

        xml_files = [
            file
            for file in os.listdir(document_local_path)
            if file.lower().endswith(".xml")
        ]

        assert len(xml_files) != 0
        DocumentIndexerService.clean_up_folder(document_local_path, xml_files)

        assert os.path.exists("/tmp/indexing_data/fullrecord.xml") == False

    def test_delete_xml_fields_from_directory(self):
        document_local_path = os.path.abspath("/tmp/indexing_data/")

        xml_files = [
            file
            for file in os.listdir(document_local_path)
            if file.lower().endswith(".xml")
        ]

        DocumentIndexerService.clean_up_folder(document_local_path, xml_files)

        assert os.path.exists("/tmp/indexing_data/fullrecord.xml") == False
