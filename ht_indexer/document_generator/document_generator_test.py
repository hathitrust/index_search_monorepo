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

        zip_path = f'{Path(os.getcwd()).parent}/data/document_generator/39015051333915.zip'
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

        catalog_fields = []
        catalog_non_fields = []
        for field in ["id", "vol_id", "coll_id", "ht_cover_tag", "ht_page_feature", "ht_reading_order",
                      "ht_scanning_order", "ht_heldby", "ht_heldby_brlm", "numPages", "numChars", "charsPerPage", "seq",
                      "pgnum", "type_s", "chunk_seq", "title", "rights", "mainauthor", "author", "author2", "date",
                      "timestamp", "record_no", "allfields", "lccn", "ctrlnum", "rptnum", "sdrnum", "oclc", "isbn",
                      "issn", "ht_id_display", "isn_related", "callnumber", "sudoc", "language", "format", "htsource",
                      "publisher", "edition", "Vauthor", "author_top", "author_rest", "authorSort", "author_sortkey",
                      "vtitle", "title_c", "title_sortkey", "title_display", "volume_enumcron", "titleSort", "Vtitle",
                      "title_ab", "title_a", "title_top", "title_rest", "series", "series2", "serialTitle_ab",
                      "serialTitle_a", "serialTitle", "serialTitle_rest", "topicStr",
                      "fullgenre", "genre", "hlb3Str", "hlb3Delimited", "publishDate", "enumPublishDate",
                      "bothPublishDate", "era", "geographicStr", "fullgeographic", "countryOfPubStr", "ocr"]:
            if field not in doc_metadata.get('content').get('response').get('docs')[0]:
                catalog_non_fields.append(field)

        print(catalog_fields)

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


