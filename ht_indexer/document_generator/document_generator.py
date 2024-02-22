import argparse
import zipfile

from catalog_metadata.catalog_metadata import CatalogItemMetadata
from ht_utils.ht_mysql import HtMysql
from ht_utils.ht_logger import get_ht_logger
from ht_utils.text_processor import string_preparation
from document_generator.mysql_data_extractor import MysqlMetadataExtractor

import xml.sax.saxutils

import lxml.etree
import io

import document_generator.mets_file_extractor
import ht_document.ht_document

logger = get_ht_logger(name=__name__)


class DocumentGenerator:
    def __init__(self, db_conn: HtMysql, catalog_api=None):
        self.mysql_data_extractor = MysqlMetadataExtractor(db_conn)
        self.catalogApi = catalog_api

    @staticmethod
    def create_ocr_field(document_zip_path: str) -> dict:
        # TODO: As part of this function we could extract the following attributes
        #  numPages, numChars, charsPerPage. In the future, these attributes could be use to measure query performance
        logger.info(f"Reading {document_zip_path}.zip file")
        full_text = DocumentGenerator.get_full_text_field(f"{document_zip_path}.zip")
        return {"ocr": full_text}

    @staticmethod
    def create_allfields_field(fullrecord_field: str) -> dict:
        # TODO Create a different class to manage the XML files
        allfields = DocumentGenerator.get_allfields_field(fullrecord_field)
        return {"allfields": allfields}

    @staticmethod
    def get_full_text_field(zip_doc_path: str):
        """
        Concatenate the content of all the .TXT files inside the input folder and return the plain string

        :param zip_doc_path: Path of the folder with list of files
        :return: String concatenated all the content of the .TXT files
        """

        full_text = ""
        logger.info("=================")
        logger.info(f"Document path {zip_doc_path}")
        try:
            zip_doc = zipfile.ZipFile(zip_doc_path, mode="r")
            for i_file in zip_doc.namelist():
                if zip_doc.getinfo(i_file).filename.endswith(".txt"):
                    full_text = (
                            full_text + " " + string_preparation(zip_doc.read(i_file))
                    )
        except Exception as e:
            logger.error(f"Something wrong with your zip file {e}")
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

        xml_string_like_file = io.BytesIO(catalog_xml.encode(encoding="utf-8"))

        for event, element in lxml.etree.iterparse(
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
                    logger.info(f"Element tag is not an integer value {e}")
                    pass
        return xml.sax.saxutils.quoteattr(allfields)

    def make_full_text_search_document(self, ht_document: ht_document.ht_document.HtDocument,
                                       doc_metadata: CatalogItemMetadata) -> dict:
        # TODO Check exception if doc_id is None
        """
        Receive the HtDocument object and the metadata from the Catalog API and generate the full text search entry
        :param ht_document:
        :param doc_metadata:
        :return: a dictionary with the full text search entry
        """
        entry = {"id": ht_document.document_id}

        # Generate ocr field
        entry.update(DocumentGenerator.create_ocr_field(ht_document.source_path))

        # Generate allfields field from fullrecord field
        # This field is in Catalog object, we process it here and after that we delete because it is not
        # necessary to be in Solr index
        entry.update(
            DocumentGenerator.create_allfields_field(doc_metadata.metadata.get("fullrecord"))
        )

        doc_metadata.metadata.pop("fullrecord")

        # Add Catalog fields to full-text document
        entry.update(doc_metadata.metadata)

        # Retrieve data from MariaDB
        entry.update(self.mysql_data_extractor.retrieve_mysql_data(ht_document.document_id))

        # Extract fields from METS file
        mets_obj = document_generator.mets_file_extractor.MetsAttributeExtractor(f"{ht_document.source_path}.mets.xml")

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
