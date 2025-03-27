import zipfile
import time

from document_generator.mysql_data_extractor import MysqlMetadataExtractor
from ht_utils.ht_mysql import HtMysql
from ht_utils.ht_logger import get_ht_logger
from ht_utils.text_processor import string_preparation
from pathlib import Path

import xml.sax.saxutils

import lxml.etree
import io

import document_generator.mets_file_extractor
import ht_document.ht_document

logger = get_ht_logger(name=__name__)


def extract_fields_from_mets_file(doc_source_path) -> dict:
    """Read the METS file and extract the fields to be used in the full-text search entry
    :param doc_source_path: Path to the document source
    :return: a dictionary with the METS fields
    """
    mets_fields = {}
    try:
        if not Path(f"{doc_source_path}.mets.xml").is_file():
            raise FileNotFoundError(f"File {doc_source_path}.mets.xml not found")
        mets_obj = document_generator.mets_file_extractor.MetsAttributeExtractor(f"{doc_source_path}.mets.xml")
        mets_entry = mets_obj.create_mets_entry()

        mets_fields["ht_page_feature"] = mets_entry.get("METS_maps").get("features")
        mets_fields.update(mets_entry.get("METS_maps").get("reading_orders"))

        return mets_fields
    except Exception as e:
        logger.error(f"Error generating METS fields {e}")
        raise e


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
            logger.error(f"Error generating the OCR field {document_zip_path}.zip {e}")
            raise e

    @staticmethod
    def create_allfields_field(fullrecord_field: str) -> dict:
        # TODO Create a different class to manage the XML files
        try:
            all_fields = FullTextDocumentGenerator.get_all_fields_field(fullrecord_field)
            return {"allfields": all_fields}
        except Exception as e:
            logger.error(f"Error generating the allfields field {e}")
            raise e

    @staticmethod
    def txt_files_2_full_text(zip_doc: zipfile.ZipFile):
        """
        Read all .TXT files in a zip and concatenate their contents.
        :return: Single string with all text files concatenated.
        """

        # Get only .txt files and sort them by name
        txt_files = sorted([i_file for i_file in zip_doc.namelist() if
                     i_file.endswith('.txt') and not i_file.startswith('__MACOSX/')])

        full_text_parts = [string_preparation(zip_doc.read(f)) for f in txt_files]

        return " ".join(full_text_parts)

    @staticmethod
    def get_full_text_field(zip_doc_path: str):
        """
        Concatenate the content of all the .TXT files inside the input folder and return the plain string

        :param zip_doc_path: Path of the folder with list of files
        :return: String concatenated all the content of the .TXT files
        """

        logger.info(f"Document path {zip_doc_path}")

        file_path = Path(zip_doc_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"File {zip_doc_path} not found")

        with zipfile.ZipFile(zip_doc_path, mode="r") as zip_doc:
            full_text = FullTextDocumentGenerator.txt_files_2_full_text(zip_doc)
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
        entry.update(FullTextDocumentGenerator.create_ocr_field(doc.source_path))

        # Generate allfields field from fullrecord field
        # This field is in a Catalog object, we process it here, and after that we delete because it is not
        # necessary to be in Solr index
        entry.update(
            FullTextDocumentGenerator.create_allfields_field(doc_metadata.get("fullrecord"))
        )
        doc_metadata.pop("fullrecord")
        logger.info(f"Time to generate process=OCR_field ht_id={doc.document_id} Time={time.time() - start}")

        # Add Catalog fields to the full-text document
        entry.update(doc_metadata)

        start = time.time()
        # Retrieve data from MariaDB
        entry.update(self.mysql_data_extractor.retrieve_mysql_data(doc.document_id))
        logger.info(f"Time to generate process=MySQL_fields ht_id={doc.document_id} Time={time.time() - start}")

        start = time.time()
        # Extract fields from METS file
        entry.update(extract_fields_from_mets_file(doc.source_path))
        logger.info(f"Time to generate process=METS_fields ht_id={doc.document_id} Time={time.time() - start}")
        entry.pop("ht_id")
        return entry
