import os
from pathlib import Path

import pytest
import pytest_cov

from document_generator.document_generator import DocumentGenerator
from xml.sax.saxutils import quoteattr
from ht_indexer_api.ht_indexer_api import HTSolrAPI


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
        """Defoe, Daniel, 1661?-1731. Rābinsan Krūso kā itihāsa. The adventures of Robinson Crusoe, translated [into Hindi] by Badrī Lāla, from a Bengali version ... Benares, 1860 455 p. incl. front., illus. plates. 20 cm. Title from Catalogue of Hindi books in the British museum. Badarīnātha, pandit, tr. Robinson Crusoe. UTL 9662 SPEC HUB PR 3403 .H5 39015078560292""")


@pytest.fixture()
def get_document_generator():
    db_conn = None
    solr_api = HTSolrAPI(url="http://192.168.112.2:9033/solr/#/catalog/")

    document_generator = DocumentGenerator(db_conn, solr_api)

    return document_generator


class TestDocumentGenerator:
    def test_get_item_htsource(self):
        htsource = DocumentGenerator.get_item_htsource("mdp.39015061418433",  # it is in solr core 7
                                                       ["University of Michigan", "Indiana University"],
                                                       ["mdp.39015061418433",
                                                        "inu.30000108625017"],
                                                       )
        assert htsource == "University of Michigan"

        htsource = DocumentGenerator.get_item_htsource("inu.30000108625017",  # it is in solr core 7
                                                       ["University of Michigan", "Indiana University"],
                                                       ["mdp.39015061418433",
                                                        "inu.30000108625017"],
                                                       )
        assert htsource == "Indiana University"

    def test_get_item_htsource_sharinghtsource(self):
        htsource = DocumentGenerator.get_item_htsource("inu.30000108625017",  # it is in solr core 7
                                                       ["University of Michigan"],
                                                       ["mdp.39015061418433",
                                                        "inu.30000108625017"],
                                                       )
        assert htsource == "University of Michigan"

    def test_not_exist_zip_file_full_text_field(self):
        with pytest.raises(Exception) as e:
            DocumentGenerator.get_full_text_field("data/test.zip")
        assert e.type == TypeError

    def test_full_text_field(self):
        zip_path = f"{Path(__file__).parents[1]}/data/document_generator/39015078560292_test.zip"
        full_text = DocumentGenerator.get_full_text_field(zip_path)

        assert len(full_text) > 10

    def test_create_allfields_field(self, get_fullrecord_xml, get_allfield_string):
        allfield = DocumentGenerator.get_allfields_field(get_fullrecord_xml)
        assert len(allfield.strip()) == len(get_allfield_string.strip())
        assert allfield.strip() == get_allfield_string.strip()

    def test_get_volume_enumcron_empty(self):
        # TODO: Check if is correct the generation of volume_enumcrom (line 417: https://github.com/hathitrust/slip-lib/blob/master/Document/Doc/vSolrMetadataAPI/Schema_LS_11.pm)
        """
        Some documents do not have the field volume_enumcrom, that is because it is an empty string in the second position.
        Is that correct
        :return:
        """
        volume_enumcrom = ""
        ht_id_display = [
            "mdp.39015078560292|20220910||1860|1860-1869|||RÄ\x81binsan KrÅ«so kÄ\x81 itihÄ\x81sa. The adventures of Robinson Crusoe, translated [into Hindi] by BadrÄ« LÄ\x81la, from a Bengali version ..."
        ]
        assert volume_enumcrom == ht_id_display[0].split("|")[2]

    def test_get_records(self, get_document_generator):
        query = "ht_id:nyp.33433082046503"
        doc_metadata = get_document_generator.get_record_metadata(query)

        assert "nyp.33433082046503" in doc_metadata.get("content").get("response").get(
            "docs"
        )[0].get("ht_id")

    def test_create_entry(self, get_document_generator):
        """
        Test the function that creates the entry with fields retrieved from Catalog index
        :return:
        """

        query = "ht_id:nyp.33433082046503"
        doc_metadata = get_document_generator.get_record_metadata(query)

        assert "nyp.33433082046503" in doc_metadata.get("content").get("response").get(
            "docs"
        )[0].get("ht_id")
