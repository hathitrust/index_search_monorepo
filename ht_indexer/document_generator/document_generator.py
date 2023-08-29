import argparse
import json
import logging
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

logging.basicConfig(level=logging.DEBUG)

from typing import Dict, List
from ht_indexer_api.ht_indexer_api import HTSolrAPI
from document_generator.indexer_config import (
    IDENTICAL_CATALOG_METADATA,
    RENAMED_CATALOG_METADATA,
    MAX_ITEM_IDS,
)
from lxml import etree
from io import BytesIO

from utils.ht_mysql import create_mysql_conn, query_mysql
from utils.ht_pairtree import download_document_file
from document_generator.mets_file_extractor import MetsAttributeExtractor

solr_api = HTSolrAPI(url="http://solr-sdr-catalog:9033/solr/#/catalog/")


def create_solr_string(data_dic: Dict) -> str:
    """
    Convert a dictionary into an xml string uses for indexing a document in Solr index.

    :param data_dic: Dictionary with the data will be indexed in Solr
    :return: XML String  with tag <add> for adding the document in Solr
    """
    solr_str = ""
    for key, values in data_dic.items():
        if not isinstance(values, List):
            solr_str = solr_str + f'<field name="{key}">{values}</field>' + "\n"
        else:
            if values:
                for value in values:
                    solr_str = solr_str + f'<field name="{key}">{value}</field>' + "\n"
    return f"<add><doc>{solr_str}</doc></add>"


def string_preparation(doc_content: BytesIO) -> str:
    """
    Clean up a byte object and convert ir to string.

    :param doc_content: XML string
    :return:
    """
    try:
        # Convert byte to str
        str_content = str(doc_content.decode())
    except Exception as e:
        try:
            str_content = str(doc_content.decode(encoding="latin1"))
            logging.info(f"File encode compatible with latin1 {e}")
        except Exception as e:
            logging.info(f"There are especial characters on the file {e}")
            raise Exception

    # Remove line breaks
    str_content = str_content.replace("\n", " ")

    # Remove extra white spaces
    str_content = re.sub(" +", " ", str_content)
    return quoteattr(str_content)


def get_full_text_field(zip_doc_path: str):
    """
    Concatenate the content of all the .TXT files inside the input folder and return the plain string.

    :param zip_doc_path: Path of the folder with list of files
    :return: String concatenated all the content of the .TXT files
    """
    full_text = ""
    try:
        zip_doc = zipfile.ZipFile(zip_doc_path, mode="r")
        for i_file in zip_doc.namelist():
            if zip_doc.getinfo(i_file).filename.endswith(".txt"):
                full_text = full_text + " " + string_preparation(zip_doc.read(i_file))
    except Exception as e:
        logging.ERROR(f"Something wring with your zip file {e}")
    full_text = full_text.encode().decode()
    return full_text


def get_allfields_field(catalog_xml: str = None) -> str:
    """
    Create a string using some of the values of the MARC XML file.

    :param catalog_xml: Path to the MARC XML file
    :return:
    """
    allfields = ""

    xml_string_like_file = BytesIO(catalog_xml.encode(encoding="utf-8"))

    for event, element in etree.iterparse(
            xml_string_like_file,
            events=("start", "end"),
    ):
        if element.tag.find("datafield") > -1:
            tag_att = element.attrib.get("tag")
            try:
                if int(tag_att) > 99 and event == "start":
                    # Looks for subfields
                    childs = [child for child in element]
                    if len(childs) > 0:
                        for child in childs:
                            allfields = allfields + " " + str(child.text)
                    else:
                        if element.text:
                            allfields = allfields + " " + str(element.text)
            except ValueError as e:
                logging.info(f"Element tag is not an integer value {e}")
                pass
    return quoteattr(allfields.strip())


def get_record_metadata(query: str = None) -> Dict:
    """
    Query Solr using and API.

    :param query: input query
    :return dictionary with the API result
    """
    response = solr_api.get_documents(query)

    return {
        "status": response.status_code,
        "description": response.headers,
        "content": json.loads(response.content.decode("utf-8")),
    }


def get_volume_enumcron(ht_id_display: str = None):
    enumcron = ht_id_display[0].split("|")[2]
    return enumcron


def get_item_htsource(
        id: str = None, catalog_htsource: List = None, catalog_htid: List = None
):
    """
    In catalog it could be a list of sources, should obtain the source of an specific item.
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

    volume_enumcron = get_volume_enumcron(metadata.get("ht_id_display"))
    if len(volume_enumcron) > 1:
        entry["volume_enumcron"] = volume_enumcron
    entry["htsource"] = get_item_htsource(
        doc_id, metadata.get("htsource"), metadata.get("ht_id")
    )

    for field in RENAMED_CATALOG_METADATA.keys():
        renamed_field = RENAMED_CATALOG_METADATA[field]
        entry[renamed_field] = metadata.get(field)

    return entry


def add_large_coll_id_field(db_conn, doc_id):
    """
    Get the list of coll_ids for the given id that are large so those coll_ids can be added as <coll_id> fields of the Solr doc.

    So, if sync-i found an id to have, erroneously, a *small* coll_id
    field in its Solr doc and queued it for re-indexing, this routine
    would create a Solr doc not containing that coll_id among its
    <coll_id> fields.
    """
    query_coll_item = (
        f'SELECT MColl_ID FROM mb_coll_item WHERE extern_item_id="{doc_id}"'
    )

    query_large_coll = (
        f"SELECT MColl_ID FROM mb_collection WHERE num_items>{MAX_ITEM_IDS}"
    )

    coll_id_entry = query_mysql(db_conn, query=query_coll_item)
    coll_id_large_entry = query_mysql(db_conn, query=query_large_coll)

    return coll_id_entry, coll_id_large_entry


def retrieve_mysql_data(db_conn, doc_id):
    entry = {}

    doc_rights = add_right_field(db_conn, doc_id)

    # Only one element
    if len(doc_rights) == 1:
        entry.update({"rights": doc_rights[0].get("attr")})

    # It is a list of members, if the query result is empty the field does not appear in Solr index
    ht_heldby = add_ht_heldby_field(db_conn, doc_id)
    if len(ht_heldby) > 0:
        list_members = [member_id.get("member_id") for member_id in ht_heldby]
        entry.update({"ht_heldby": list_members})

    # It is a list of members, if the query result is empty the field does not appear in Solr index
    heldby_brlm = add_add_heldby_brlm_field(db_conn, doc_id)
    if len(heldby_brlm) > 0:
        list_brl_members = [member_id.get("member_id") for member_id in heldby_brlm]
        entry.update({"ht_heldby_brlm": list_brl_members})

    # It is a list of coll_id, if the query result is empty, the value of this field in Solr index will be [0]
    coll_id_result, large_coll_id_result = add_large_coll_id_field(db_conn, doc_id)
    if len(coll_id_result) > 0:
        list_coll_ids = [coll_id.get("MColl_ID") for coll_id in coll_id_result]
        list_large_coll_id = [
            coll_id.get("MColl_ID") for coll_id in large_coll_id_result
        ]

        entry.update({"coll_id": list(set(list_coll_ids) & set(list_large_coll_id))})
    else:
        entry.update({"coll_id": [0]})
    return entry


def add_right_field(db_conn, doc_id) -> Dict:
    namespace, id = doc_id.split(".")
    query = f'SELECT * FROM rights_current WHERE namespace="{namespace}" AND id="{id}"'
    slip_rights_entry = query_mysql(db_conn, query=query)
    return slip_rights_entry


def add_ht_heldby_field(db_conn, doc_id) -> Dict:
    query = f'SELECT member_id FROM holdings_htitem_htmember WHERE volume_id="{doc_id}"'

    ht_heldby_entry = query_mysql(db_conn, query=query)
    # ht_heldby is a list of institutions
    return ht_heldby_entry


def add_add_heldby_brlm_field(db_conn, doc_id) -> Dict:
    query = f'SELECT member_id FROM holdings_htitem_htmember WHERE volume_id="{doc_id}" AND access_count > 0'

    ht_heldby_entry = query_mysql(db_conn, query=query)
    return ht_heldby_entry


def main():
    """
    Receive a document id and a zip file path.
    :return: XML file

    Steps:
    Unzip file

    - Query catalog to retrieve document metadata
    - Generate full_text field
    - Generate allfield field from MAC.xml
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc_id", help="document ID", required=True, default=None)
    parser.add_argument(
        "--mysql_host", help="Host to connect to MySql server", required=True
    )
    parser.add_argument(
        "--mysql_user", help="User to connect to MySql server", required=True
    )
    parser.add_argument(
        "--mysql_pass", help="Password to connect to MySql server", required=True
    )
    parser.add_argument("--mysql_database", help="MySql database", required=True)

    args = parser.parse_args()

    db_conn = create_mysql_conn(
        host=args.mysql_host,
        user=args.mysql_user,
        password=args.mysql_pass,
        database=args.mysql_database,
    )

    # Query solr index with the document id
    query = f"ht_id:{args.doc_id}"
    doc_metadata = get_record_metadata(query)

    # Download document .zip and .mets.xml file
    target_path = f"{Path(__file__).parents[1]}/data/document_generator"
    download_document_file(
        doc_name=args.doc_id, target_path=target_path, extension="zip"
    )

    # Add Catalog fields to full-text document
    entry = create_full_text_entry(
        args.doc_id, doc_metadata.get("content").get("response").get("docs")[0]
    )

    # Retrieve document full-text
    obj_id = args.doc_id.split(".")[1]
    full_text = get_full_text_field(
        f"{Path(__file__).parents[1]}/data/document_generator/{obj_id}.zip"
    )  # args.zip_file_path
    entry.update({"ocr": full_text})

    # Get allfields entry
    full_record_entry = (
        doc_metadata.get("content").get("response").get("docs")[0].get("fullrecord")
    )

    entry["allfields"] = get_allfields_field(full_record_entry)

    # Extract fields from MySql database
    mysql_entry = retrieve_mysql_data(db_conn, args.doc_id)

    entry.update(mysql_entry)

    ####### Extract fields from METS file

    # Download document .zip and .mets.xml file
    target_path = f"{Path(__file__).parents[1]}/data/document_generator"

    download_document_file(
        doc_name=args.doc_id, target_path=target_path, extension="mets.xml"
    )

    namespace, obj_id = args.doc_id.split(".")

    mets_obj = MetsAttributeExtractor(f"{target_path}/{obj_id}.mets.xml")

    mets_entry = mets_obj.create_mets_entry()

    entry.update({"ht_page_feature": mets_entry.get("METS_maps").get("features")})
    entry.update(mets_entry.get("METS_maps").get("reading_orders"))

    solr_str = create_solr_string(entry)

    with open(
            f"{Path(__file__).parents[1]}/ht_indexer_api/data/add/{obj_id}_solr_full_text.xml",
            "w",
    ) as f:
        f.write(solr_str)


if __name__ == "__main__":
    main()
