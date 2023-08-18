import argparse
import zipfile
import logging
import re
import json

from typing import Dict
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from document_generator.config import CATALOG_METADATA
from lxml import etree

solr_api = HTSolrAPI(url="http://localhost:9033/solr/#/catalog/")

def create_solr_string(data_dic: Dict) -> str:

    solr_str = ''
    for key, values in data_dic.items():
        if isinstance(values, str):
            solr_str = solr_str + f'<field name=\"{key}\">{values}</field>'+'\n'
        else:
            for value in values:
                solr_str = solr_str + f'<field name=\"{key}\">{value}</field>'+'\n'
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

def get_allfields_field(catalog_xml_string: str):
    allfields = ''

    # Read XML file
    #parser = etree.XMLParser(catalog_xml_string)  # ElementTree.parse('schema.xml')
    tree = etree.XML(catalog_xml_string)

    # col_names = ["name", "type", "indexed", "stored", "multiValued"]

    root = tree.getroot()

    schema_fields_dic = {}
    for field in root.findall('field'):
        schema_fields_dic[field.attrib['name']] = field.attrib
        schema_fields_dic[field.attrib['name']].update({'schema.xml': 'Exist'})
        schema_fields_dic[field.attrib['name']].update({'origen': ''})

    return allfields

def get_record_metadata(query: str = None):

    response = solr_api.get_documents(query)

    return {'status': response.status_code,
            'description': response.headers,
            'content': json.loads(response.content.decode('utf-8'))}

    return response

def create_full_text_entry(metadata: Dict) -> Dict:

    entry = {}
    for field in CATALOG_METADATA:
        entry[field] = metadata.get(field)

    return entry

"""
Mysql queries

# Retrieve sysid for item_id and construct query, How to obtain the nid???
    SELECT sysid FROM slip_rights WHERE nid=?

"""

def add_right_field():
    return {'rights': None}

def add_ht_heldby_field():
    return {'ht_heldby': None}

def add_add_heldby_brlm_field():
    return {'ht_page_feature': None}

def add_ht_page_feature_field():
    pass

def add_add_reading_order():
    return {'ht_reading_order': None,
            'ht_scanning_order': None,
            'ht_cover_tag': None
            }

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
    parser.add_argument('--zip_file_path', help='Zip file with document files', required=True)

    args = parser.parse_args()

    full_text = get_full_text_field(args.zip_file_path)

    #allfield_field =

    # Query solr index with the document id
    #query = {'ht_id': args.doc_id} #'mdp.39015084393423'
    query = f'ht_id:{args.doc_id}'
    doc_metadata = get_record_metadata(query)

    with open("../ht_indexer_api/data/add/full_record.xml", "w") as f:
        f.write(doc_metadata.get('content').get('response').get('docs')[0].get('fullrecord'))

    entry = create_full_text_entry(doc_metadata.get('content').get('response').get('docs')[0])

    entry.update({'ocr': full_text})

    solr_str = create_solr_string(entry)

    #tree = ET.XMl(solr_str)
    with open("../ht_indexer_api/data/add/myfirstSolrDoc.xml", "w") as f:
        f.write(solr_str)#




if __name__ == "__main__":
    main()