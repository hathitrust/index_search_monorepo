from pathlib import Path

import pytest

# relative imports
from document_generator.full_text_document_generator import FullTextDocumentGenerator
from ht_utils.testing import capture_logs

# A single MARC datafield whose tag is filled in by each test case.
MARC_XML_SINGLE_DATAFIELD = """
    <record>
        <datafield tag="{tag}" ind1=" " ind2=" ">
            <subfield code="a">001718542</subfield>
        </datafield>
    </record>
"""

# Nonstandard 999-style tags that some MARC records carry. Shared by both tests below.
NON_NUMERIC_TAGS = [
    pytest.param("CID", id="cid"),
    pytest.param("HOL", id="hol"),
    pytest.param("FMT", id="fmt"),
    pytest.param("DAT", id="dat"),
    pytest.param("CAT", id="cat"),
]


class TestFullTextDocumentGenerator:
    def test_get_all_fields_field(self) -> None:
        path = f"{Path(__file__).parents[1]}/document_generator_tests/data/fullrecord.xml"
        res = FullTextDocumentGenerator.get_all_fields_field(Path(path).read_text())
        # The actual length for the fixture we're using is about 350.
        # Assert the order of magnitude.
        assert len(res) > 100 and len(res) < 1000

    @pytest.mark.parametrize("tag", NON_NUMERIC_TAGS)
    def test_get_all_fields_field_skips_non_numeric_tag_silently(self, tag: str) -> None:
        marc_xml = MARC_XML_SINGLE_DATAFIELD.format(tag=tag)

        with capture_logs() as entries:
            FullTextDocumentGenerator.get_all_fields_field(marc_xml)

        assert not any(
            e.get("event", "").startswith("Element tag is not an integer value") for e in entries
        )

    @pytest.mark.parametrize("tag", NON_NUMERIC_TAGS)
    def test_get_all_fields_field_non_numeric_tag_returns_empty_quoted_string(
        self, tag: str
    ) -> None:
        marc_xml = MARC_XML_SINGLE_DATAFIELD.format(tag=tag)

        res = FullTextDocumentGenerator.get_all_fields_field(marc_xml)

        # The only datafield is skipped, and `xml.sax.saxutils.quoteattr` wraps "" in quotes.
        assert res == '""'
