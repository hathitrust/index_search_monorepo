import json


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


if __name__ == "__main__":
    '''
    Usefully script for experiments.
    Script to transform a JSON file into a txt file with the ids of the documents'''

    list_id = get_first_item(document_path="id_IN_kubernetes1.json")

    with open('ids_kubernetes.txt', 'w') as f:
        f.write("\n".join(list_id))
