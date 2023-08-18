import pytest
from typing import Dict
from document_generator import get_allfields_field, get_full_text_field, get_record_metadata, create_solr_string
from config import CATALOG_METADATA
#class TestDocumentGenerator():

@pytest.fixture()
def get_fullrecord_xml():

    return """<?xml version="1.0" encoding="UTF-8"?><collection xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.loc.gov/MARC21/slim" xsi:schemaLocation="http://www.loc.gov/MARC21/slim http://www.loc.gov/standards/marcxml/schema/MARC21slim.xsd"><record><leader>00861nas a22002771a 4500</leader><controlfield tag="001">000066200</controlfield><controlfield tag="003">MiAaHDL</controlfield><controlfield tag="005">20210817000000.0</controlfield><controlfield tag="006">m d </controlfield><controlfield tag="007">cr bn ---auaua</controlfield><controlfield tag="008">880715d19851985enkmr p 0uuua0eng d</controlfield><datafield tag="010" ind1=" " ind2=" "><subfield code="a">sn 86021889</subfield></datafield><datafield tag="035" ind1=" " ind2=" "><subfield code="a">(MiU)990000662000106381</subfield></datafield><datafield tag="035" ind1=" " ind2=" "><subfield code="a">sdr-miu.990000662000106381</subfield></datafield><datafield tag="035" ind1=" " ind2=" "><subfield code="a">sdr-inu2175373</subfield></datafield><datafield tag="035" ind1=" " ind2=" "><subfield code="a">(OCoLC)13453550</subfield></datafield><datafield tag="035" ind1=" " ind2=" "><subfield code="a">(CaOTULAS)159949347</subfield></datafield><datafield tag="035" ind1=" " ind2=" "><subfield code="a">(RLIN)MIUG86-S2225</subfield></datafield><datafield tag="035" ind1=" " ind2=" "><subfield code="z">(MiU)Aleph000066200</subfield></datafield><datafield tag="040" ind1=" " ind2=" "><subfield code="a">MH</subfield><subfield code="c">MH</subfield><subfield code="d">MH</subfield><subfield code="d">MiU</subfield></datafield><datafield tag="042" ind1=" " ind2=" "><subfield code="a">lcd</subfield></datafield><datafield tag="043" ind1=" " ind2=" "><subfield code="a">e-pl---</subfield></datafield><datafield tag="245" ind1="0" ind2="0"><subfield code="a">Poland one magazine.</subfield></datafield><datafield tag="246" ind1="1" ind2="7"><subfield code="a">Poland one</subfield></datafield><datafield tag="260" ind1=" " ind2=" "><subfield code="a">London :</subfield><subfield code="b">Polish Cultural Foundation,</subfield><subfield code="c">1985.</subfield></datafield><datafield tag="300" ind1=" " ind2=" "><subfield code="a">1 v. :</subfield><subfield code="b">ill. ;</subfield><subfield code="c">30 cm.</subfield></datafield><datafield tag="362" ind1="0" ind2=" "><subfield code="a">Vol. 1, no. 9 (Feb. 1985)-v. 1, no. 12 (May 1985).</subfield></datafield><datafield tag="500" ind1=" " ind2=" "><subfield code="a">Title from cover.</subfield></datafield><datafield tag="538" ind1=" " ind2=" "><subfield code="a">Mode of access: Internet.</subfield></datafield><datafield tag="651" ind1=" " ind2="0"><subfield code="a">Poland</subfield><subfield code="x">Periodicals.</subfield></datafield><datafield tag="710" ind1="2" ind2=" "><subfield code="a">Polish Cultural Foundation (London, England)</subfield></datafield><datafield tag="780" ind1="0" ind2="0"><subfield code="t">Poland one</subfield><subfield code="x">0266-1993</subfield><subfield code="w">(DLC)sn 86021892</subfield></datafield><datafield tag="CID" ind1=" " ind2=" "><subfield code="a">000066200</subfield></datafield><datafield tag="DAT" ind1="0" ind2=" "><subfield code="a">19950609000000.0</subfield><subfield code="b">20210817000000.0</subfield></datafield><datafield tag="DAT" ind1="1" ind2=" "><subfield code="a">20210921060726.0</subfield><subfield code="b">2021-11-13T18:34:01Z</subfield></datafield><datafield tag="CAT" ind1=" " ind2=" "><subfield code="a">SDR-MIU</subfield><subfield code="d">ALMA</subfield><subfield code="l">prepare.pl-004-008</subfield></datafield><datafield tag="FMT" ind1=" " ind2=" "><subfield code="a">SE</subfield></datafield><datafield tag="HOL" ind1=" " ind2=" "><subfield code="0">sdr-miu.990000662000106381</subfield><subfield code="a">MiU</subfield><subfield code="b">SDR</subfield><subfield code="c">MIU</subfield><subfield code="p">mdp.39015061418433</subfield><subfield code="s">MIU</subfield><subfield code="z">v.1 no.8-12</subfield><subfield code="1">990000662000106381</subfield></datafield><datafield tag="974" ind1=" " ind2=" "><subfield code="b">MIU</subfield><subfield code="c">MIU</subfield><subfield code="d">20211113</subfield><subfield code="s">google</subfield><subfield code="u">mdp.39015061418433</subfield><subfield code="z">v.1 no.8-12</subfield><subfield code="y">1985</subfield><subfield code="r">und</subfield><subfield code="q">bib</subfield><subfield code="t">non-US bib date1 &gt;= 1928</subfield></datafield><datafield tag="974" ind1=" " ind2=" "><subfield code="b">INU</subfield><subfield code="c">INU</subfield><subfield code="d">20220315</subfield><subfield code="s">google</subfield><subfield code="u">inu.30000108625017</subfield><subfield code="z">v.1,no.9-12 1985</subfield><subfield code="y">1985</subfield><subfield code="r">ic</subfield><subfield code="q">bib</subfield><subfield code="t">non-US serial item date &gt;= 1928</subfield></datafield></record></collection>"""
def test_not_exist_zip_file_full_text_field():
    with pytest.raises(Exception) as e:
        get_full_text_field('data/test.zip')
    assert e.type == TypeError

def test_full_text_field():

    full_text = get_full_text_field('data/33433075969752.zip')

    assert len(full_text) > 10


def test_create_allfields_field(get_fullrecord_xml):

    assert len(get_allfields_field(get_fullrecord_xml)) > 0



def test_get_records():

    query = "ht_id:mdp.39015084393423"
    doc_metadata = get_record_metadata(query)
    #print(doc_metadata)

    #assert type(doc_metadata.get('content').get('response').get('docs')[0]) == Dict
    assert "mdp.39015084393423" in doc_metadata.get('content').get('response').get('docs')[0].get('ht_id')

    catalog_fields = []
    catalog_non_fields = []
    for field in ["id", "vol_id","coll_id","ht_cover_tag","ht_page_feature","ht_reading_order",
                  "ht_scanning_order","ht_heldby","ht_heldby_brlm","numPages","numChars","charsPerPage","seq",
                  "pgnum","type_s","chunk_seq","title","rights","mainauthor","author","author2","date",
                  "timestamp","record_no","allfields","lccn","ctrlnum","rptnum","sdrnum","oclc","isbn",
                  "issn","ht_id_display","isn_related","callnumber","sudoc","language","format","htsource",
                  "publisher","edition","Vauthor","author_top","author_rest","authorSort","author_sortkey",
                  "vtitle","title_c","title_sortkey","title_display","volume_enumcron","titleSort","Vtitle",
                  "title_ab","title_a","title_top","title_rest","series","series2","serialTitle_ab",
                  "serialTitle_a","serialTitle","serialTitle_rest","topicStr",
                  "fullgenre","genre","hlb3Str","hlb3Delimited","publishDate","enumPublishDate",
                  "bothPublishDate","era","geographicStr","fullgeographic","countryOfPubStr","ocr"]:
        if field not in doc_metadata.get('content').get('response').get('docs')[0]:
            catalog_non_fields.append(field)

    print(catalog_fields)

def test_create_solr_string():

    """
    Test the function that generate the string in XTML format we will index in full-text search index
    :return:
    """
    data_dic = {"sdrnum": ["sdr-txu-1.b25999849", "sdr-txu-1.b25999850"],
                "title": "test XML output format"}
    solr_string = create_solr_string(data_dic)
    print(solr_string)
    assert """<doc><field name="sdrnum">sdr-txu-1.b25999849</field>
    <field name="sdrnum">sdr-txu-1.b25999850</field>
    <field name="title">test XML output format</field>
    </doc>""" == solr_string

def test_create_entry():

    """
    Test the function that creates the entry with fields retrieved from Catalog index
    :return:
    """

    query = "ht_id:mdp.39015084393423"
    doc_metadata = get_record_metadata(query)

