import argparse
import json
import logging

import zipfile
from xml.sax.saxutils import quoteattr

logging.basicConfig(level=logging.DEBUG)

from typing import Dict, List
from document_generator.indexer_config import (
    IDENTICAL_CATALOG_METADATA,
    RENAMED_CATALOG_METADATA,
    MAX_ITEM_IDS,
)
from lxml import etree
from io import BytesIO

from utils.ht_mysql import query_mysql
from document_generator.mets_file_extractor import MetsAttributeExtractor
from utils.text_processor import string_preparation

from ht_document.ht_document import HtDocument


class DocumentGenerator:
    def __init__(self, db_conn, catalogApi=None):
        self.db_conn = db_conn
        self.catalogApi = catalogApi

    def get_record_metadata(self, query: str = None) -> Dict:
        """
        API call to query Catalog Solr index
        :param query: input query
        :return dictionary with the API result

        """
        response = self.catalogApi.get_documents(query)

        return {
            "status": response.status_code,
            "description": response.headers,
            "content": json.loads(response.content.decode("utf-8")),
        }

    @staticmethod
    def make_solr_query(doc_id):
        query = f"ht_id:{doc_id}"
        return query

    @staticmethod
    def get_catalog_identical_fiels(metadata: Dict) -> Dict:
        entry = {}
        for field in IDENTICAL_CATALOG_METADATA:
            value = metadata.get(field)
            if value:
                entry[field] = value
        return entry

    @staticmethod
    def rename_catalog_fields(metadata: Dict) -> Dict:
        entry = {}
        for field in RENAMED_CATALOG_METADATA.keys():
            renamed_field = RENAMED_CATALOG_METADATA[field]
            entry[renamed_field] = metadata.get(field)
        return entry

    @staticmethod
    def get_volume_enumcron(ht_id_display: str = None):
        enumcron = ht_id_display[0].split("|")[2]
        return enumcron

    @staticmethod
    def get_item_htsource(
        id: str = None, catalog_htsource: List = None, catalog_htid: List = None
    ):
        """
        In catalog it could be a list of sources, should obtain the source of an specific item
        :param id: Catalod ht_id field
        :param catalog_htsource: catalog item source
        :param catalog_htid: catalog item ht_id
        :return:
        """
        item_position = catalog_htid.index(id)
        try:
            htsource = catalog_htsource[item_position]
        except IndexError as e:
            htsource = catalog_htsource[0]
        return htsource

    @staticmethod
    def retrieve_fields_from_Catalog_index(doc_id: str, metadata: Dict) -> Dict:
        entry = {}

        entry.update(DocumentGenerator.get_catalog_identical_fiels(metadata))
        entry.update(DocumentGenerator.rename_catalog_fields(metadata))

        volume_enumcron = DocumentGenerator.get_volume_enumcron(
            metadata.get("ht_id_display")
        )
        if len(volume_enumcron) > 1:
            entry["volume_enumcron"] = volume_enumcron
        entry["htsource"] = DocumentGenerator.get_item_htsource(
            doc_id, metadata.get("htsource"), metadata.get("ht_id")
        )
        return entry

    @staticmethod
    def create_ocr_field(document_zip_path) -> Dict:
        logging.info(f"Reading {document_zip_path}.zip file")
        full_text = DocumentGenerator.get_full_text_field(f"{document_zip_path}.zip")
        return {"ocr": full_text}

    @staticmethod
    def create_allfields_field(fullrecord_field: str) -> Dict:
        # TODO Create a different class to manage the XML files
        allfields = DocumentGenerator.get_allfields_field(fullrecord_field)
        return {"allfields": allfields}

    # TODO I could have a class to retrieve data from MySql
    def add_large_coll_id_field(self, doc_id):
        """
        Get the list of coll_ids for the given id that are large so those
        coll_ids can be added as <coll_id> fields of the Solr doc.

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

        coll_id_entry = query_mysql(self.db_conn, query=query_coll_item)
        coll_id_large_entry = query_mysql(self.db_conn, query=query_large_coll)

        return coll_id_entry, coll_id_large_entry

    # TODO probably I do not need the functions below to retrieve the fields from MySql
    # I can directly call query_mysql, less lines of code
    def add_right_field(self, doc_id) -> Dict:
        namespace, id = doc_id.split(".")
        query = (
            f'SELECT * FROM rights_current WHERE namespace="{namespace}" AND id="{id}"'
        )
        slip_rights_entry = query_mysql(self.db_conn, query=query)
        return slip_rights_entry

    def add_ht_heldby_field(self, doc_id) -> Dict:
        query = (
            f'SELECT member_id FROM holdings_htitem_htmember WHERE volume_id="{doc_id}"'
        )

        ht_heldby_entry = query_mysql(self.db_conn, query=query)
        # ht_heldby is a list of institutions
        return ht_heldby_entry

    def add_add_heldby_brlm_field(self, doc_id) -> Dict:
        query = f'SELECT member_id FROM holdings_htitem_htmember WHERE volume_id="{doc_id}" AND access_count > 0'

        ht_heldby_entry = query_mysql(self.db_conn, query=query)
        return ht_heldby_entry

    def retrieve_mysql_data(self, doc_id):
        entry = {}
        logging.info((f"Retrieving data from MySql {doc_id}"))
        doc_rights = self.add_right_field(doc_id)

        # Only one element
        if len(doc_rights) == 1:
            entry.update({"rights": doc_rights[0].get("attr")})

        # It is a list of members, if the query result is empty the field does not appear in Solr index
        ht_heldby = self.add_ht_heldby_field(doc_id)
        if len(ht_heldby) > 0:
            list_members = [member_id.get("member_id") for member_id in ht_heldby]
            entry.update({"ht_heldby": list_members})

        # It is a list of members, if the query result is empty the field does not appear in Solr index
        heldby_brlm = self.add_add_heldby_brlm_field(doc_id)
        if len(heldby_brlm) > 0:
            list_brl_members = [member_id.get("member_id") for member_id in heldby_brlm]
            entry.update({"ht_heldby_brlm": list_brl_members})

        # It is a list of coll_id, if the query result is empty, the value of this field in Solr index will be [0]
        coll_id_result, large_coll_id_result = self.add_large_coll_id_field(doc_id)
        if len(coll_id_result) > 0:
            list_coll_ids = [coll_id.get("MColl_ID") for coll_id in coll_id_result]
            list_large_coll_id = [
                coll_id.get("MColl_ID") for coll_id in large_coll_id_result
            ]

            entry.update(
                {"coll_id": list(set(list_coll_ids) & set(list_large_coll_id))}
            )
        else:
            entry.update({"coll_id": [0]})
        return entry

    @staticmethod
    def get_full_text_field(zip_doc_path: str):
        """
        Concatenate the content of all the .TXT files inside the input folder and return the plain string

        :param zip_doc_path: Path of the folder with list of files
        :return: String concatenated all the content of the .TXT files
        """

        full_text = ""
        print("=================")
        print(zip_doc_path)
        try:
            zip_doc = zipfile.ZipFile(zip_doc_path, mode="r")
            for i_file in zip_doc.namelist():
                if zip_doc.getinfo(i_file).filename.endswith(".txt"):
                    full_text = (
                        full_text + " " + string_preparation(zip_doc.read(i_file))
                    )
        except Exception as e:
            logging.ERROR(f"Something wring with your zip file {e}")
        full_text = full_text.encode().decode()
        return full_text

    @staticmethod
    def get_allfields_field(catalog_xml: str = None) -> str:
        """
        Create a string using some of the values of the MARC XML file
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
                                allfields = allfields.strip() + " " + str(child.text)
                        else:
                            if element.text:
                                allfields = allfields.strip() + " " + str(element.text)
                except ValueError as e:
                    logging.info(f"Element tag is not an integer value {e}")
                    pass
        return quoteattr(allfields)

    # TODO Check exception if doc_id is None
    def make_full_text_search_document(
        self, ht_document: HtDocument, doc_metadata: Dict
    ) -> Dict:
        """
        Receive the ht_id and create the HtDocument entry
        :param ht_document:
        :param doc_id:
        :param doc_metadata:
        :return:
        """
        entry = {"id": ht_document.document_id}

        # Add Catalog fields to full-text document
        entry.update(
            DocumentGenerator.retrieve_fields_from_Catalog_index(
                ht_document.document_id, doc_metadata
            )
        )

        # Generate ocr field
        entry.update(DocumentGenerator.create_ocr_field(ht_document.target_path))

        logging.info(doc_metadata)
        # Generate allfields field
        entry.update(
            DocumentGenerator.create_allfields_field(doc_metadata.get("fullrecord"))
        )

        # Retrieve data from MariaDB
        entry.update(self.retrieve_mysql_data(ht_document.document_id))

        # Extract fields from METS file
        mets_obj = MetsAttributeExtractor(f"{ht_document.target_path}.mets.xml")

        mets_entry = mets_obj.create_mets_entry()

        entry.update({"ht_page_feature": mets_entry.get("METS_maps").get("features")})
        entry.update(mets_entry.get("METS_maps").get("reading_orders"))

        return entry


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
    parser.add_argument("--doc_id", help="document ID", required=True, default=None)


if __name__ == "__main__":
    main()
