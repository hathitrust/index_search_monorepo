"""
This script is used to generate the full text search entries for a list of ht_id defined in a TXT file
"""
import argparse
import inspect
import json
import os
import sys

from catalog_metadata.catalog_metadata import CatalogRecordMetadata
from document_generator.document_generator import DocumentGenerator
from document_retriever_service.catalog_retriever_service import CatalogRetrieverService
from document_retriever_service.full_text_search_retriever_service import FullTextSearchRetrieverService
from document_retriever_service.ht_status_retriever_service import get_non_processed_ids
from document_retriever_service.retriever_arguments import RetrieverServiceArgumentsByFile
from ht_document.ht_document import logger
from ht_indexer_api.ht_indexer_api import HTSolrAPI

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)


class FullTextSearchRetrieverServiceByFile(FullTextSearchRetrieverService):

    def __init__(self, catalog_api: HTSolrAPI,
                 document_generator_obj: DocumentGenerator = None,
                 document_local_path: str = None, document_local_folder: str = None
                 ):
        FullTextSearchRetrieverService.__init__(self, catalog_api, document_generator_obj,
                                                document_local_path,
                                                document_local_folder)

    def retrieve_documents(self, query, start, rows):

        """
        This method is used to retrieve the documents from the Catalog, then it will be used to return instances
        of a CatalogMetadata
        """

        # Get list ids from query parameter
        if 'ht_id' in query and ' OR ' in query:
            list_ids = [i.strip("\)").strip('\"') for i in query.split(':(')[1].split(' OR ')]
        else:
            logger.info(f"Query {query} does not have a valid format for this use case")
            exit()

        response = self.catalog_api.get_documents(query=query, start=start, rows=rows)
        output = response.json()

        try:
            total_records = output.get("response").get("numFound")
            logger.info(total_records)
        except Exception as e:
            logger.error(f"Solr index {self.catalog_api} seems empty {e}")
            exit()
        count_records = 0
        while count_records < total_records:
            results = []
            response = self.catalog_api.get_documents(
                query=query, start=start, rows=rows
            )

            output = json.loads(response.content.decode("utf-8"))

            # TODO: Add a check to verify if the response is empty

            for record in output.get("response").get("docs"):
                count_records = count_records + 1

                catalog_record_metadata = CatalogRecordMetadata(record)

                for item_id in record.get('ht_id'):  # Append list of CatalogMetadata object
                    if item_id in list_ids:
                        results.append(CatalogRetrieverService.get_catalog_object(record, item_id,
                                                                                  catalog_record_metadata))

            logger.info(f"Batch documents {count_records}")
            start += rows
            logger.info(f"Result length {len(results)}")
            yield results


def main():
    parser = argparse.ArgumentParser()
    init_args_obj = RetrieverServiceArgumentsByFile(parser)

    document_indexer_service = FullTextSearchRetrieverServiceByFile(init_args_obj.solr_api_catalog,
                                                                    init_args_obj.document_generator,
                                                                    init_args_obj.document_local_path,
                                                                    init_args_obj.document_local_folder)

    # TODO: Review the logic of the status file
    status_file = os.path.join(parent, "document_retriever_status.txt")

    if init_args_obj.list_ids_path:
        # If a document with the list of id to process is received as a parameter, then create batch of queries
        with open(init_args_obj.list_ids_path) as f:
            list_ids = f.read().splitlines()

            ids2process, processed_ids = get_non_processed_ids(status_file, list_ids)

            logger.info(f"Total of items to process {len(ids2process)}")

            tmp_file_status = open(os.path.join(init_args_obj.document_local_path, "document_retriever_status.txt"),
                                   "w+")
            for doc in processed_ids:
                tmp_file_status.write(doc + "\n")
            tmp_file_status.close()

            while ids2process:
                chunk, ids2process = ids2process[:5], ids2process[5:]
                values = "\" OR \"".join(chunk)
                values = '"'.join(("", values, ""))
                query = f"ht_id:({values})"

                # Create queries that contain a list of ht_id
                document_indexer_service.full_text_search_retriever_service(
                    query,
                    init_args_obj.start,
                    init_args_obj.rows,
                    document_repository=init_args_obj.document_repository)
    else:
        logger.info("Provide the file with the list of ids to process is a required parameter")
        exit()


if __name__ == "__main__":
    main()
