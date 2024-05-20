import zipfile
import time
import os

from document_generator.mysql_data_extractor import MysqlMetadataExtractor
from ht_utils.ht_mysql import HtMysql
from ht_utils.ht_logger import get_ht_logger
from ht_utils.text_processor import string_preparation

import xml.sax.saxutils

import lxml.etree
import io

import document_generator.mets_file_extractor
import ht_document.ht_document

logger = get_ht_logger(name=__name__)


class FullTextDocumentGenerator:

    def __init__(self, db_conn: HtMysql):
        self.mysql_data_extractor = MysqlMetadataExtractor(db_conn)

    @staticmethod
    def create_ocr_field(document_zip_path: str) -> dict:
        # TODO: As part of this function we could extract the following attributes
        #  numPages, numChars, charsPerPage. In the future, these attributes could be use to measure query performance
        logger.info(f"Reading {document_zip_path}.zip file")

        try:
            full_text = FullTextDocumentGenerator.get_full_text_field(f"{document_zip_path}.zip")
            return {"ocr": full_text}
        except Exception as e:
            logger.error(f"Error reading file {document_zip_path}.zip {e}")
            raise e

    @staticmethod
    def create_allfields_field(fullrecord_field: str) -> dict:
        # TODO Create a different class to manage the XML files
        all_fields = FullTextDocumentGenerator.get_all_fields_field(fullrecord_field)
        return {"allfields": all_fields}

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
        if not os.path.isfile(zip_doc_path):
            raise FileNotFoundError(f"File {zip_doc_path} not found")

        zip_doc = zipfile.ZipFile(zip_doc_path, mode="r")
        for i_file in zip_doc.namelist():
            if zip_doc.getinfo(i_file).filename.endswith(".txt"):
                full_text = (
                        full_text + " " + string_preparation(zip_doc.read(i_file))
                )

        full_text = full_text.encode().decode()
        return full_text

    @staticmethod
    def get_all_fields_field(catalog_xml: str = None) -> str:
        """
        Create a string using some of the values of the MARC XML file
        :param catalog_xml: Path to the MARC XML file
        :return:
        """

        all_fields = ""

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
                                all_fields = all_fields.strip() + " " + str(child.text)
                        else:
                            if element.text:
                                all_fields = all_fields.strip() + " " + str(element.text)
                except ValueError as e:
                    logger.info(f"Element tag is not an integer value {e}")
                    pass
        return xml.sax.saxutils.quoteattr(all_fields)

    def make_full_text_search_document(self, doc: ht_document.ht_document.HtDocument,
                                       doc_metadata: dict) -> dict:
        # TODO Check exception if doc_id is None
        """
        Receive the HtDocument object and the metadata from the Catalog API and generate the full text search entry
        :param doc:
        :param doc_metadata:
        :return: a dictionary with the full text search entry
        """
        entry = {"id": doc.document_id}

        start = time.time()

        # Generate ocr field and check if the current document is a valid UTF-8 encoded document
        try:
            entry.update(FullTextDocumentGenerator.create_ocr_field(doc.source_path))
        except Exception as e:
            logger.error(f"Error generating the OCR field {doc.source_path}.zip {e}")
            raise e

        # Generate allfields field from fullrecord field
        # This field is in Catalog object, we process it here and after that we delete because it is not
        # necessary to be in Solr index
        try:
            entry.update(
                FullTextDocumentGenerator.create_allfields_field(doc_metadata.get("fullrecord"))
            )
        except Exception as e:
            logger.error(f"Error generating the allfields field {e}")
            raise e

        doc_metadata.pop("fullrecord")

        logger.info(f"Time to generate OCR field {doc.document_id} {time.time() - start}")

        # Add Catalog fields to full-text document
        entry.update(doc_metadata)

        start = time.time()
        # Retrieve data from MariaDB
        try:
            entry.update(self.mysql_data_extractor.retrieve_mysql_data(doc.document_id))
        except Exception as e:
            logger.error(f"Error retrieving MySQL data {e}")
            raise e

        logger.info(f"Time to generate MySQL fields {doc.document_id} {time.time() - start}")

        start = time.time()
        # Extract fields from METS file
        try:
            mets_obj = document_generator.mets_file_extractor.MetsAttributeExtractor(f"{doc.source_path}.mets.xml")

            mets_entry = mets_obj.create_mets_entry()

            entry.update({"ht_page_feature": mets_entry.get("METS_maps").get("features")})
            entry.update(mets_entry.get("METS_maps").get("reading_orders"))
        except Exception as e:
            logger.error(f"Error generating METS fields {e}")
            raise e
        logger.info(f"Time to generate METS fields {doc.document_id} {time.time() - start}")
        entry.pop("ht_id")
        return entry
