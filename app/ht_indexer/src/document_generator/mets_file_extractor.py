import argparse
from pathlib import Path

from ht_utils.ht_logger import get_ht_logger
from lxml import etree

logger = get_ht_logger(name=__name__)


class MetsAttributeExtractor:
    def __init__(self, path):
        self.tree = etree.parse(path)
        self.namespace = self.tree.getroot().nsmap

    def create_mets_map(self) -> dict:
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
        for _key, value in mets_map.items():
            if "," in value.get("features"):
                for item in value.get("features").split(", "):
                    all_features.append(item.strip(""))
            else:
                all_features.append(value.get("features").strip(""))
        return list(set(all_features))

    def create_mets_entry(self):
        logger.info("Creating METS map")
        mets_map = self.create_mets_map()

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

    namespace, obj_id = args.doc_id.split(".")

    mets_obj = MetsAttributeExtractor(f"{target_path}/{obj_id}.mets.xml")

    mets_entry = mets_obj.create_mets_entry()

    logger.info(mets_entry.get("METS_maps").get("ht_page_feature"))


if __name__ == "__main__":
    main()
