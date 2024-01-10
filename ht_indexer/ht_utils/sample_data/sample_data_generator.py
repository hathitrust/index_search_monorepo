from ht_document.ht_document import HtDocument
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

from random import shuffle
import json
import os
import inspect
from typing import List

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))


def get_percentage(lst: List, percentage: float):
    shuffle(lst)
    result = []
    for _ in range(int(len(lst) * float(percentage))):
        result.append(lst.pop())
    return result


def get_ht_id_source_path(ht_id):
    ht_document = HtDocument(document_id=ht_id, document_repository="pairtree")

    return ht_document.source_path


def generate_sample_data(percentage=0.010, all_items: bool = False):
    """Input: JSON file with the items indexed in Catalog test image
    Use this cur command to Generate the json with the Catalog ids
    ```curl "http://localhost:9033/solr/catalog/select?q=*%3A*&wt=json&indent=true&start=0&rows=2000000000&&fl=id,ht_id" > full-output-catalog-index.json```
    We need the ht_id to retrieve the zip and mets file. However, the id in Catalog is used to freely re-distribute the
    texts.
    Procedure: Select from Catalog N percentage of items to index
        Parameter to decide if you want to index all items or the first one from Catalog index ,
        Download the ZIP file
    """

    catalog_json_file = open(f"{currentdir}/full-output-catalog-index.json", "r")

    catalog_id = json.loads(catalog_json_file.read())

    logger.info(f"Total records in Catalog: {len(catalog_id)}")
    doc_ids_sample = get_percentage(catalog_id, percentage)

    logger.info(f"Total of Catalog record to download files {len(doc_ids_sample)}")

    sample_data_path = []
    sample_data_ht_id = []
    if all_items:
        # Download all the items of Catalog record
        for item in doc_ids_sample:
            for ht_id in item.get("ht_id", []):
                sample_data_ht_id.append(ht_id)
                sample_data_path.append(f"{get_ht_id_source_path(ht_id)}.zip")
                sample_data_path.append(f"{get_ht_id_source_path(ht_id)}.mets.xml")

    else:
        # Download only one item per Catalog record
        for item in doc_ids_sample:
            for ht_id in item.get("ht_id", []):
                sample_data_ht_id.append(ht_id)
                sample_data_path.append(f"{get_ht_id_source_path(ht_id)}.zip")
                sample_data_path.append(f"{get_ht_id_source_path(ht_id)}.mets.xml")
                break

    with open(
            f"{currentdir}/sample_data_path.txt",
            "w",
    ) as newfile:
        data2write = "\n".join(sample_data_path)
        newfile.write(data2write)

    with open(
            f"{currentdir}/sample_data_ht_ids.txt",
            "w",
    ) as newfile:
        data2write = "\n".join(sample_data_ht_id)
        newfile.write(data2write)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(".env")

    generate_sample_data(
        percentage=os.environ.get("SAMPLE_PERCENTAGE", 0.01),
        all_items=os.environ.get("ALL_ITEMS", False)
    )
