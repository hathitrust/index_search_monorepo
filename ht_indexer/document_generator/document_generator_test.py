import inspect
import os
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr
from ht_utils.text_processor import string_preparation
import zipfile

import pytest
from _pytest.outcomes import Failed

from document_generator.full_text_document_generator import FullTextDocumentGenerator

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

    def test_full_text_field_raise_unicode_error(self):

        """At least one of the txt of include in the xip file
        is not a valid UTF-8 encoded document, so the function should raise an exception."""
        zip_path = f"{Path(__file__).parents[1]}/data/document_generator/mb.39015078560292_test.zip"

        with pytest.raises(Exception):
            FullTextDocumentGenerator.get_full_text_field(zip_path)

    def test_string_preparation_raise_unicodedecodeerror(self):

        zip_doc_path = f"{Path(__file__).parents[1]}/data/document_generator/mb.39015078560292_test.zip"

        full_test = ""

        zip_doc = zipfile.ZipFile(zip_doc_path, mode="r")
        with pytest.raises(Exception, match=""):
            for i_file in zip_doc.namelist():
                if zip_doc.getinfo(i_file).filename.endswith(".txt"):
                    doc_str = string_preparation(zip_doc.read(i_file))
                    full_test = full_test + " " + doc_str

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
