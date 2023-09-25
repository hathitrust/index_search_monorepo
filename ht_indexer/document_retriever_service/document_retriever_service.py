class DocumentRetrieverService:
    def retrieve_documents(self):
        raise NotImplementedError("not method to retrieve documents")


"""
class DocumentRetrievalService:
    def __init__(self, catalogApi=None, solr_api_full_text=None):
        self.catalogApi = catalogApi
        self.solr_api_full_text = solr_api_full_text

    def get_record_metadata(self, query: str = None) -> Dict:
        
        API call to query Catalog Solr index
        :param query: input query
        :return dictionary with the API result

        
        response = self.catalogApi.get_documents(query)

        return {
            "status": response.status_code,
            "description": response.headers,
            "content": json.loads(response.content.decode("utf-8")),
        }

    def retrieve_documents(self):

        query = "*:*"
        start = 0
        rows = 100
        total_htid = 0
        total_records = 0
        result = {'response': {}, 'docs': []}
        results = []

        while result:
            response = self.catalogApi.get_documents(query=query, start=start,
                                                     rows=rows)

            batch_record = 0

            for record in response:
                batch_record = batch_record + 1
                output = json.loads(record.content.decode("utf-8"))

                result = output.get("response").get("docs")
                results.append(result)

            # batch_documents = batch_documents + total_htid
            total_records = total_records + batch_record
            logging.info(f"Batch documents {total_records}")
            start += rows
            yield results

        logging.info(f"Total of items (ht_id) {total_htid}")

    def generate_full_text_entry(self, query):

        for results in self.retrieve_documents():
            for record in results:
                for doc in record:
                    for doc_id in doc.get("ht_id"):
                        logging.info(f"Processing document {doc_id}")

                        obj_id = entry.get("id").split(".")[1]
                        logging.info(f"Processing item {obj_id}")

                        try:
                            entry = document_generator.make_document(doc_id, doc)
                            yield entry
                        except Exception as e:
                            logging.info(f"Document {doc_id} failed {e}")
                            continue

                        yield entry

        #

        for record in results:
            for doc in record.get("response").get("docs"):
                total_htid = total_htid + 1
                for doc_id in doc.get("ht_id"):
                    logging.info(f"Processing document {doc_id}")

                    yield doc_id


    @staticmethod
    def clean_up_folder(document_path, list_documents):
        logging.info("Cleaning up .xml and .Zip files")

        for id_name in list_documents:
            list_documents = glob.glob(f"{document_path}/{id_name}")
            for file in list_documents:
                logging.info(f"Deleting file {file}")
                os.remove(file)

    def indexing_documents(self, path):
        # Call API
        response = self.solr_api_full_text.index_document(path)
        return response

    def retrieve_list_ht_ids(self):

        for results in self.retrieve_documents():

            count = count + 1

            for record in results:
                for doc in record:
                    # total_htid = total_htid + 1
                    for doc_id in doc.get("ht_id"):
                        logging.info(f"Processing document {doc_id}")

                        yield doc_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--solr_url",
        help="",
        required=True,
        default="http://localhost:8983/solr/#/core-x/",
    )

    parser.add_argument(
        "--solr_indexing_api",
        help="",
        required=True,
        default="http://localhost:8082/solrIndexing/#/core-x/",
    )

    parser.add_argument(
        "--mysql_host", help="Host to connect to MySql server", required=True
    )
    parser.add_argument(
        "--mysql_user", help="User to connect to MySql server", required=True
    )
    parser.add_argument(
        "--mysql_pass", help="Password to connect to MySql server", required=True
    )
    parser.add_argument("--mysql_database", help="MySql database", required=True)

    args = parser.parse_args()

    db_conn = create_mysql_conn(
        host=args.mysql_host,
        user=args.mysql_user,
        password=args.mysql_pass,
        database=args.mysql_database,
    )

    solr_api_catalog = HTSolrAPI(url=args.solr_url)
    solr_api_full_text = HTSolrAPI(url=args.solr_indexing_api)

    document_retrieval_service = DocumentRetrievalService(
        solr_api_catalog, solr_api_full_text
    )

    count = 0
    list_ids = []
    # TODO How can I paralelize the process of retrieving documents from solr Catalog?

    file_object = open("items_list.txt", "w+")

    # Print ids
    for ht_id in document_retrieval_service.retrieve_list_ht_ids():
        file_object.write(f"{ht_id}\n")
    file_object.close()
    print(count)

    document_local_path = "/tmp"
    document_generator = DocumentGenerator(self.db_conn)
    for entry in document_retrieval_service.generate_full_text_entry():

        solr_str = create_solr_string(entry)

        list_ids.append(obj_id)
        with open(
                f"/tmp/{obj_id}_solr_full_text.xml",
                "w",
        ) as f:
            f.write(solr_str)

        if len(list_ids) >= 10:
            logging.info(f"Indexing documents: {list_ids}")
            response = document_retrieval_service.indexing_documents(
                document_local_path
            )

            if response.status_code == 200:
                DocumentRetrievalService.clean_up_folder(document_local_path, list_ids)

            list_ids = []

    if len(list_ids) > 0:
        logging.info(f"Indexing documents: {list_ids}")
        response = document_retrieval_service.indexing_documents(document_local_path)

        if response.status_code == 200:
            DocumentRetrievalService.clean_up_folder(document_local_path, list_ids)

    logging.info(f"Indexed {count} records")


if __name__ == "__main__":
    main()
"""
