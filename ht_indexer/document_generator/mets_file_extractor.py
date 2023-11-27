import argparse

from pathlib import Path
from typing import Dict

from lxml import etree

from utils.ht_pairtree import download_document_file

from utils.ht_logger import HTLogger

logger = HTLogger(name=__file__)


class MetsAttributeExtractor:
    def __init__(self, path):
        # parser = etree.XMLParser(remove_blank_text=True)
        self.tree = etree.parse(path)
        self.namespace = self.tree.getroot().nsmap

    def create_METS_map(self) -> Dict:
        mets_map = {}

        # TODO Remove hardcode Use the namespace dictionary to find the element

        # Main element
        fptr_elem = self.tree.find("./{http://www.loc.gov/METS/}structMap")

        # Child elements
        for page_attr in fptr_elem.findall(".//{http://www.loc.gov/METS/}div[@LABEL]"):
            file_names = [i.attrib.get("FILEID") for i in page_attr.getchildren()]

            mets_map[page_attr.attrib.get("ORDER")] = {
                "filename": file_names,
                "pgnum": page_attr.attrib.get("ORDERLABEL"),
                "features": page_attr.attrib.get("LABEL"),
            }

        return mets_map

    def get_reading_order(self):
        # Extract from MET.xml file

        reading_order_info = {}

        # TODO Remove hardcode Use the namespace dictionary to find the element
        xml_data_elem = self.tree.find(".//{http://www.loc.gov/METS/}xmlData")

        for elem in xml_data_elem.getchildren():
            for url in self.namespace.values():
                if url in elem.tag:
                    key_name = elem.tag.replace(f"{url}", "")
                    reading_order_info.update({key_name.strip("{}"): elem.text})
                    break

        return reading_order_info

    @staticmethod
    def get_unique_features(mets_map):
        all_features = []
        for key, value in mets_map.items():
            if "," in value.get("features"):
                for item in value.get("features").split(", "):
                    all_features.append(item.strip(""))
            else:
                all_features.append(value.get("features").strip(""))
        return list(set(all_features))

    def create_mets_entry(self):
        logger.info("Creating METS map")
        mets_map = self.create_METS_map()

        logger.info("Creating METS entry")
        features = MetsAttributeExtractor.get_unique_features(mets_map)

        logger.info("Retrieving document orders")
        reading_order = self.get_reading_order()

        return {
            "is_valid": 0,
            "METS_filelist": [],
            "METS_has_files": 0,
            "METS_maps": {
                "seq2pgnum": {},
                "features": features,
                "reading_orders": {
                    "ht_scanning_order": reading_order.get("scanningOrder"),
                    "ht_reading_order": reading_order.get("readingOrder"),
                    "ht_cover_tag": reading_order.get("coverTag"),
                },
            },
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc_id", help="document ID", required=True, default=None)

    args = parser.parse_args()

    # Download document .zip and .mets.xml file
    target_path = f"{Path(__file__).parents[1]}/data/document_generator"

    download_document_file(
        doc_name=args.doc_id, target_path=target_path, extension="mets.xml"
    )

    namespace, obj_id = args.doc_id.split(".")

    mets_obj = MetsAttributeExtractor(f"{target_path}/{obj_id}.mets.xml")

    mets_entry = mets_obj.create_mets_entry()

    logger.info(mets_entry.get("METS_maps").get("ht_page_feature"))


if __name__ == "__main__":
    main()
