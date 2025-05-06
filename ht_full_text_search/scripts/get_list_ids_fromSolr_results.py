import json
import os
from pathlib import Path
from argparse import ArgumentParser

from ht_full_text_search.config_search import FULL_TEXT_SOLR_URL, CATALOG_SOLR_URL
from ht_full_text_search.export_all_results import SolrExporter
from ht_full_text_search.config_files import config_files_path

#current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
#parent = os.path.dirname(current)
#sys.path.insert(0, parent)

def get_first_item(document_path: str) -> list:
    """
    Function that reads a JSON file to create a list with documents ids.
    Args:
        document_path (str): Path to the JSON file.
    Returns:
        list_ids (list): List of ids from the JSON file.
    """

    list_ids = []
    with open(document_path, "r") as f:
        data = json.load(f)

        for record in data['response']['docs']:
            list_ids.append(record["id"])
    return list_ids


def main():

    parser = ArgumentParser()
    parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))
    parser.add_argument("--solr_host", help="Solr url", default=None)
    parser.add_argument("--collection_name", help="Name of the collection", default=None)
    parser.add_argument("--cluster_name", help="It can be catalog or fulltext", required=True)
    parser.add_argument("--file_name", help="Name od the file to load the list of ids", required=True)

    args = parser.parse_args()

    # Default parameters are for full-text search
    solr_host = FULL_TEXT_SOLR_URL[args.env]
    config_files = 'full_text_search'
    conf_query = "ocr"

    # Overwrite default parameter for Catalog search
    if args.cluster_name == "catalog":
        solr_host = CATALOG_SOLR_URL[args.env]
        config_files = 'catalog_search'
        conf_query = "all"

    if args.solr_host:
        solr_base_url = f"{args.solr_host}/solr/{args.collection_name}"
    else:
        solr_base_url = f"{solr_host}/solr/{args.collection_name}"


    query_config_file_path = Path(config_files_path, f'{config_files}/config_query.yaml')

    query = "*:*"
    solr_exporter = SolrExporter(solr_base_url, args.env,
                                     user=os.getenv("SOLR_USER"), password=os.getenv("SOLR_PASSWORD"))
    # '"good"'
    list_documents = []
    for x in solr_exporter.run_cursor(query, query_config_file_path, conf_query=conf_query,
                                      list_output_fields=["id", "ht_id"]):
        dict_x = json.loads(x)
        if "ht_id" in dict_x:
            list_documents.extend([ht_id for ht_id in dict_x["ht_id"]])
        if len(list_documents) >= 1000000:
            break

    # Write the IDs to a file
    with open(args.file_name, "w") as file:
        for _id in list_documents:
            file.write(f"{_id}\n")

    print(f"File '{args.file_name}' created successfully!")

if __name__ == "__main__":
    '''
    Usefully script for experiments.
    Script to transform a JSON file into a txt file with the ids of the documents'''

    main()
    #list_id = get_first_item(document_path="id_IN_kubernetes1.json")

    #with open('ids_kubernetes.txt', 'w') as f:
    #    f.write("\n".join(list_id))
