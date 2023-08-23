import pytest
from pytest import fixture
from pathlib import Path
import os

from document_generator.document_generator import get_allfields_field, get_full_text_field, get_record_metadata, \
    create_solr_string, get_item_htsource


@pytest.fixture()
def get_fullrecord_xml():
    with open(f'{Path(os.getcwd()).parent}/data/document_generator/fullrecord.xml', 'r') as f:
        full_record_data = f.read()
    return full_record_data


@pytest.fixture()
def get_allfield_string():
    return """Poland one magazine. Poland one London : Polish Cultural Foundation, 1985. 1 v. : ill. ; 30 cm. Vol. 1, no. 9 (Feb. 1985)-v. 1, no. 12 (May 1985). Title from cover. Mode of access: Internet. Poland Periodicals. Polish Cultural Foundation (London, England) Poland one 0266-1993 (DLC)sn 86021892 MIU MIU 20211113 google mdp.39015061418433 v.1 no.8-12 1985 und bib non-US bib date1 >= 1928 INU INU 20220315 google inu.30000108625017 v.1,no.9-12 1985 1985 ic bib non-US serial item date >= 1928"""


class TestDocumentGenerator:

    def test_get_item_htsource(self):
        htsource = get_item_htsource("mdp.39015061418433",
                                     ["University of Michigan", "Indiana University"],
                                     ["mdp.39015061418433", "inu.30000108625017"]
                                     )
        assert htsource == "University of Michigan"

    def test_not_exist_zip_file_full_text_field(self):
        with pytest.raises(Exception) as e:
            get_full_text_field('data/test.zip')
        assert e.type == TypeError

    def test_full_text_field(self):

        zip_path = f'{Path(os.getcwd()).parent}/data/document_generator/39015078560292_test.zip'
        full_text = get_full_text_field(zip_path)

        assert len(full_text) > 10

    def test_create_allfields_field(self, get_fullrecord_xml, get_allfield_string):

        allfield = get_allfields_field(get_fullrecord_xml)
        assert len(allfield.strip()) == len(get_allfield_string.strip())
        assert allfield.strip() == get_allfield_string.strip()

    def test_get_records(self):

        query = "ht_id:mdp.39015084393423"
        doc_metadata = get_record_metadata(query)

        assert "mdp.39015084393423" in doc_metadata.get('content').get('response').get('docs')[0].get('ht_id')

    def test_create_solr_string(self):

        """
        Test the function that generate the string in XML format we will index in full-text search index
        :return:
        """
        data_dic = {"sdrnum": ["sdr-txu-1.b25999849", "sdr-txu-1.b25999850"],
                    "title": "test XML output format"}
        solr_string = create_solr_string(data_dic)

        assert len("""<doc> <field name="sdrnum">sdr-txu-1.b25999849</field> <field name="sdrnum">sdr-txu-1.b25999850</field> <field name="title">test XML output format</field></doc>""") == len(solr_string)

    def test_create_entry(self):

        """
        Test the function that creates the entry with fields retrieved from Catalog index
        :return:
        """

        query = "ht_id:mdp.39015084393423"
        doc_metadata = get_record_metadata(query)

        assert "mdp.39015084393423" in doc_metadata.get('content').get('response').get('docs')[0].get("ht_id")


    def test_get_volume_enumcron_empty(self):
        # TODO: Check if is correct the generation of volume_enumcrom (line 417: https://github.com/hathitrust/slip-lib/blob/master/Document/Doc/vSolrMetadataAPI/Schema_LS_11.pm)
        """
        Some documents do not have the field volume_enumcrom, that is because it is an empty string in the second position.
        Is that correct
        :return:
        """
        volume_enumcrom=''
        ht_id_display = ['mdp.39015078560292|20220910||1860|1860-1869|||RÄ\x81binsan KrÅ«so kÄ\x81 itihÄ\x81sa. The adventures of Robinson Crusoe, translated [into Hindi] by BadrÄ« LÄ\x81la, from a Bengali version ...'
]
        assert volume_enumcrom == ht_id_display[0].split('|')[2]


