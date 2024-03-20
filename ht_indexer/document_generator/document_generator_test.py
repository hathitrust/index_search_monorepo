import inspect
import os
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

import pytest
from _pytest.outcomes import Failed

from document_generator.document_generator import DocumentGenerator

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
        try:
            with pytest.raises(Exception):
                DocumentGenerator.get_full_text_field("data/test.zip")
        except Failed:
            pass

    def test_full_text_field(self):
        zip_path = f"{Path(__file__).parents[1]}/data/document_generator/mb.39015078560292_test.zip"
        full_text = DocumentGenerator.get_full_text_field(zip_path)

        assert len(full_text) > 10

    def test_create_allfields_field(self, get_fullrecord_xml, get_allfield_string):
        allfield = DocumentGenerator.get_allfields_field(get_fullrecord_xml)
        assert len(allfield.strip()) == len(get_allfield_string.strip())
        assert allfield.strip() == get_allfield_string.strip()
