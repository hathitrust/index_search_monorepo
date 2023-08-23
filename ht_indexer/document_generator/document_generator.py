import argparse
import zipfile
import logging
import re
import json
import os
from pathlib import Path

logging.basicConfig(level=logging.DEBUG)

from typing import Dict, List
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from indexer_config import IDENTICAL_CATALOG_METADATA, RENAMED_CATALOG_METADATA
from lxml import etree
from io import BytesIO


from utils.ht_mysql import create_mysql_conn, query_mysql
from utils.ht_pairtree import download_document_file

solr_api = HTSolrAPI(url="http://localhost:9033/solr/#/catalog/")


def create_solr_string(data_dic: Dict) -> str:
    solr_str = ''
    for key, values in data_dic.items():
        if isinstance(values, str):
            solr_str = solr_str + f'<field name=\"{key}\">{values}</field>' + '\n'
        else:
            if values:
                for value in values:
                    solr_str = solr_str + f'<field name=\"{key}\">{value}</field>' + '\n'
    return f'<doc>{solr_str}</doc>'


def string_preparation(doc_content):
    """
    Receive a byte object and return str
    :param doc_content:
    :return:
    """

    # Convert byte to str
    str_content = str(doc_content.decode())

    # Remove line breaks
    str_content = str_content.replace("\n", " ")

    # Remove extra white spaces
    str_content = re.sub(' +', ' ', str_content)
    return str_content


def get_full_text_field(zip_doc_path):
    full_text = ''
    try:
        zip_doc = zipfile.ZipFile(zip_doc_path, mode='r')
        for i_file in zip_doc.namelist():
            if zip_doc.getinfo(i_file).filename.endswith('.txt'):
                full_text = full_text + ' ' + string_preparation(zip_doc.read(i_file))
    except Exception as e:
        logging.ERROR(f'Something wring with your zip file {e}')
    return full_text


def get_allfields_field(catalog_xml: str = None):
    allfields = ''

    xml_string_like_file = BytesIO(catalog_xml.encode(encoding='utf-8'))

    for event, element in etree.iterparse(xml_string_like_file, events=("start", "end"), ):
        if element.tag.find("datafield") > -1:
            tag_att = element.attrib.get('tag')
            try:
                if int(tag_att) > 99 and event == "start":
                    # Looks for subfields
                    childs = [child for child in element]
                    if len(childs) > 0:
                        for child in childs:
                            allfields = allfields + ' ' + str(child.text)
                    else:
                        if element.text:
                            allfields = allfields + ' ' + str(element.text)
            except ValueError as e:
                logging.info(f'Element tag is not an integer value {e}')
                continue
    return allfields


def get_record_metadata(query: str = None):
    response = solr_api.get_documents(query)

    return {'status': response.status_code,
            'description': response.headers,
            'content': json.loads(response.content.decode('utf-8'))}

    return response


def get_volume_enumcron(ht_id_display: str = None):
    enumcron = ht_id_display[0].split('|')[2]
    return enumcron


def get_item_htsource(id: str = None, catalog_htsource: List = None, catalog_htid: List = None):
    """
    In catalog it could be a list of sources, should obtain the source of an specific item
    :param id: Catalod ht_id field
    :param catalog_htsource: catalog item source
    :param catalog_htid: catalog item ht_id
    :return:
    """
    item_position = catalog_htid.index(id)
    htsource = catalog_htsource[item_position]

    return htsource


def create_full_text_entry(doc_id: str, metadata: Dict) -> Dict:
    entry = {}
    for field in IDENTICAL_CATALOG_METADATA:
        value = metadata.get(field)
        if value:
            entry[field] = value

    volume_enumcron = get_volume_enumcron(metadata.get('ht_id_display'))
    if len(volume_enumcron) > 1:
        entry['volume_enumcron'] = volume_enumcron
    entry['htsource'] = get_item_htsource(doc_id, metadata.get('htsource'), metadata.get('ht_id'))

    for field in RENAMED_CATALOG_METADATA.keys():
        renamed_field = RENAMED_CATALOG_METADATA[field]
        entry[renamed_field] = metadata.get(field)

    return entry


"""
Mysql queries

# Retrieve sysid for item_id and construct query, How to obtain the nid???
    SELECT sysid FROM slip_rights WHERE nid=?

"""
def add_large_coll_id_field():

    """
    Get the list of coll_ids for the given id that are large so those
    coll_ids can be added as <coll_id> fields of the Solr doc.

    So, if sync-i found an id to have, erroneously, a *small* coll_id
    field in its Solr doc and queued it for re-indexing, this routine
    would create a Solr doc not containing that coll_id among its
    <coll_id> fields.
    """


def retrieve_mysql_data(db_conn, doc_id):
    entry = {}

    # Retrieve vol_id
    vol_id = "mdp.39015078560292"

    doc_rights = add_right_field(db_conn, doc_id)
    if doc_rights.get('attr'):
        entry.update({'rights': doc_rights.get('attr')})

    ht_heldby = add_ht_heldby_field(db_conn, vol_id)
    if ht_heldby.get('member_id'):
        entry.update({'ht_heldby': ht_heldby.get('member_id')})

    heldby_brlm = add_add_heldby_brlm_field(db_conn, vol_id)
    if heldby_brlm.get('member_id'):
        entry.update({'ht_heldby_brlm': heldby_brlm.get('member_id')})
    return entry


def add_right_field(db_conn, doc_id) -> Dict:
    namespace, id = doc_id.split('.')
    query = f"SELECT * FROM rights_current WHERE namespace=\"{namespace}\" AND id=\"{id}\""
    slip_rights_entry = query_mysql(db_conn, query=query)
    return slip_rights_entry


def add_ht_heldby_field(db_conn, vol_id) -> Dict:

    query = f"SELECT member_id FROM holdings_htitem_htmember WHERE volume_id=\"{vol_id}\""

    ht_heldby_entry = query_mysql(db_conn, query=query)
    #ht_heldby is a list of institutions
    return ht_heldby_entry


def add_add_heldby_brlm_field(db_conn, vol_id="mdp.39015078560292") -> Dict:

    query = f"SELECT member_id FROM holdings_htitem_htmember WHERE volume_id=\"{vol_id}\" AND access_count > 0"

    ht_heldby_entry = query_mysql(db_conn, query=query)
    return ht_heldby_entry


def add_ht_page_feature_field():
    # Extract from MET.xml file
    pass


def add_add_reading_order():
    # Extract from MET.xml file
    return {'ht_reading_order': None,
            'ht_scanning_order': None,
            'ht_cover_tag': None
            }


# MySql queries


def main():
    """
    Receive a document id and a zip file path
    :return: XML file

    Steps:
    Unzip file

    - Query catalog to retrieve document metadata
    - Generate full_text field
    - Generate allfield field from MAC.xml
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('--doc_id', help='document ID', required=True, default=None)
    #parser.add_argument('--zip_file_path', help='Zip file with document files', required=True)
    parser.add_argument('--mysql_host', help='Host to connect to MySql server', required=True)
    parser.add_argument('--mysql_user', help='User to connect to MySql server', required=True)
    parser.add_argument('--mysql_pass', help='Password to connect to MySql server', required=True)
    parser.add_argument('--mysql_database', help='MySql database', required=True)

    args = parser.parse_args()

    db_conn = create_mysql_conn(host=args.mysql_host, user=args.mysql_user,
                                password=args.mysql_pass, database=args.mysql_database)

    # Query solr index with the document id
    # query = {'ht_id': args.doc_id} #'mdp.39015084393423'
    query = f'ht_id:{args.doc_id}'
    doc_metadata = get_record_metadata(query)

    """
    # Download document .zip and .mets.xml file
    target_path = f'{Path(__file__).parents[1]}/data/data_generator'
    download_document_file(args.doc_id, target_path)
    """
    # Add Catalog fields to full-text document
    entry = create_full_text_entry(args.doc_id, doc_metadata.get('content').get('response').get('docs')[0])

    """
    # Retrieve document full-text
    obj_id = args.doc_id.split(".")[1]
    full_text = get_full_text_field(f'../data/{obj_id}.zip')  # args.zip_file_path
    entry.update({'ocr': full_text})
    """

    # Get allfields entry
    full_record_entry = doc_metadata.get('content').get('response').get('docs')[0].get('fullrecord')
    entry['allfields'] = get_allfields_field(full_record_entry)

    # Extract fields from MySql database
    mysql_entry = retrieve_mysql_data(db_conn, args.doc_id)

    # with open("../ht_indexer_api/data/add/full_record.xml", "w") as f:
    #    f.write(doc_metadata.get('content').get('response').get('docs')[0].get('fullrecord'))

    solr_str = create_solr_string(entry)

    # tree = ET.XMl(solr_str)
    with open("../ht_indexer_api/data/add/myfirstSolrDoc.xml", "w") as f:
        f.write(solr_str)


if __name__ == "__main__":
    main()
