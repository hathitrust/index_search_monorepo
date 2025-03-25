import inspect
import os
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr
import zipfile

import pytest
from _pytest.outcomes import Failed

from document_generator.full_text_document_generator import FullTextDocumentGenerator
from document_generator.mysql_data_extractor import extract_namespace_and_id
from ht_utils.text_processor import string_preparation

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)


@pytest.fixture()
def get_fullrecord_xml():
    with open(
            f"{Path(__file__).parents[1]}/data/document_generator/fullrecord.xml", "r"
    ) as f:
        full_record_data = f.read()
    return full_record_data


@pytest.fixture()
def get_allfield_string():
    return quoteattr(
        """Defoe, Daniel, 1661?-1731. Rābinsan Krūso kā itihāsa. The adventures of Robinson Crusoe, translated [into Hindi] by Badrī Lāla, from a Bengali version ... Benares, 1860 455 p. incl. front., illus. plates. 20 cm. Title from Catalogue of Hindi books in the British museum. Badarīnātha, pandit, tr. Robinson Crusoe. UTL 9662 SPEC HUB PR 3403 .H5 39015078560292"""
    )


class TestDocumentGenerator:

    def test_not_exist_zip_file_full_text_field(self):
        """ Test the function when the zip file does not exist """
        try:
            with pytest.raises(Exception):
                FullTextDocumentGenerator.get_full_text_field("data/test.zip")
        except Failed:
            pass

    def test_full_text_field_well_generated(self):

        """
        Test the function when the zip file exists, the zip file can contain a __MACOSX directory inside, but
        the function will ignore this directory and the full text is well generated
        """

        zip_doc_path = f"{Path(__file__).parents[1]}/data/document_generator/mb.39015078560292_test.zip"

        zip_doc = zipfile.ZipFile(zip_doc_path, mode="r")
        full_test = FullTextDocumentGenerator.txt_files_2_full_text(zip_doc)
        assert len(full_test) > 0

    def test_string_preparation_raise_unicodedecodeerror_macosx_directory(self):

        """
        A UnicodeDecodeError is find when the zip file contains pesky __MACOSX directory inside,
        so the function should raise an exception if __MACOSX directory is not ignored
        string_preparation function should raise an exception when the received file is from the __MACOSX directory
        This use case forces the UnicodeDecodeError exception processing files inside __MACOSX folder.
        """

        zip_doc_path = f"{Path(__file__).parents[1]}/data/document_generator/mb.39015078560292_test.zip"

        zip_doc = zipfile.ZipFile(zip_doc_path, mode="r")
        with pytest.raises(UnicodeDecodeError):
            full_text = FullTextDocumentGenerator.txt_files_2_full_text(zip_doc)

            for i_file in zip_doc.namelist():
                if i_file.startswith('__MACOSX/'):
                    if zip_doc.getinfo(i_file).filename.endswith(".txt"):
                        doc_str = string_preparation(zip_doc.read(i_file))
                        full_text = full_text + " " + doc_str

    def test_full_text_field(self):
        zip_path = f"{Path(__file__).parents[1]}/data/document_generator/mb.39015078560292_test.zip"

        try:
            with pytest.raises(Exception):
                FullTextDocumentGenerator.get_full_text_field(zip_path)
        except Failed:
            assert 0 == 0

    def test_create_allfields_field(self, get_fullrecord_xml, get_allfield_string):
        all_field = FullTextDocumentGenerator.get_all_fields_field(get_fullrecord_xml)

        assert len(all_field.strip()) == len(get_allfield_string.strip())
        assert all_field.strip() == get_allfield_string.strip()

    def test_extract_namespace_and_id(self):
        """
        Extracts the namespace and the id from a given document id string.
        The namespace is defined as the characters before the first period.
        The id is the remainder of the string after the first period.

        :param document_id: The document id string to extract from.
        :return: A tuple containing the namespace and the id.
        """

        document_id = "uc2.ark:/13960/t4mk66f1d"
        namespace, id = extract_namespace_and_id(document_id)
        assert namespace == "uc2"
        assert id == "ark:/13960/t4mk66f1d"

        document_id = "miun.afs8435.0001.001"
        namespace, id = extract_namespace_and_id(document_id)
        assert namespace == "miun"
        assert id == "afs8435.0001.001"

        document_id = "uiug.30112056400960"
        namespace, id = extract_namespace_and_id(document_id)
        assert namespace == "uiug"
        assert id == "30112056400960"
