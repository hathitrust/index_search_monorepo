from pathlib import Path
from unittest.mock import patch

# relative imports
from document_generator.full_text_document_generator import FullTextDocumentGenerator


class TestFullTextDocumentGenerator:
    def test_get_all_fields_field(self) -> None:
        path = f"{Path(__file__).parents[1]}/document_generator_tests/data/fullrecord.xml"
        res = FullTextDocumentGenerator.get_all_fields_field(Path(path).read_text())
        # The actual length for the fixture we're using is about 350.
        # Assert the order of magnitude.
        assert len(res) > 100 and len(res) < 1000

    def test_get_all_fields_field_ignores_cid(self) -> None:
        marc_xml = """
            <record>
                <datafield tag="CID" ind1=" " ind2=" ">
                    <subfield code="a">001718542</subfield>
                </datafield>
            </record>
        """
        # The `logger.info` calls were clogging the logs. Having a CID in the MARC
        # should no longer be reported by the logger.
        with patch("document_generator.full_text_document_generator.logger") as mock_logger:
            res = FullTextDocumentGenerator.get_all_fields_field(marc_xml)
        assert mock_logger.info.call_count == 0
        # No data to extract since the only datafield is skipped. The result is quoted by
        # `xml.sax.saxutils.quoteattr` so the output is `""`.
        assert len(res) == 2
