import json

def get_first_item(document_path):

    list_ids = []
    with open(document_path, "r") as f:
        data = json.load(f)

        for record in data['response']['docs']:
            list_ids.append(record["id"])
    return list_ids

if __name__ == "__main__":

    list_id = get_first_item(document_path="id_IN_kubernetes1.json")

    with open('ids_kubernetes.txt', 'w') as f:
        f.write("\n".join(list_id))