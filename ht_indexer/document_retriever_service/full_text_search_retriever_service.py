import argparse
import inspect
import os
import sys
import catalog_metadata.catalog_metadata as catalog_metadata
from document_generator.document_generator import DocumentGenerator
from ht_utils.ht_logger import get_ht_logger
from catalog_retriever_service import CatalogRetrieverService
from ht_utils.text_processor import create_solr_string
from ht_document.ht_document import HtDocument
from document_retriever_service.retriever_arguments import RetrieverServiceArguments

logger = get_ht_logger(name=__name__)

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)


class FullTextSearchRetrieverService(CatalogRetrieverService, RetrieverServiceArguments):
    """
    This class is responsible to retrieve the documents from the Catalog and generate the full text search entry
    There are three main use cases:
        1- Retrieve all the items of a record in the Catalog - the query will contain the id of the record
        2- Retrieve a specific item of a record in the Catalog - the query will contain the ht_id of the item
        3- Retrieve all the items of all the records in the Catalog - the query will be *:*
    By default, the query is None, then an error will be raised if the query is not provided
    """

    def __init__(self, catalog_api=None,
                 document_generator_obj: DocumentGenerator = None,
                 document_local_path: str = None, document_local_folder: str = None
                 ):
        super().__init__(catalog_api)
        self.document_generator = document_generator_obj

        # TODO: Define the queue to publish the documents
        self.document_local_path = document_local_path
        self.document_local_folder = document_local_folder

        # Create the directory to load the xml files if it does not exit
        try:
            if self.document_local_path:
                document_local_path = os.path.abspath(self.document_local_path)
            os.makedirs(os.path.join(document_local_path, document_local_folder))
        except FileExistsError:
            pass

    def publish_document(self, file_name: str = None, content: str = None):
        """
        Right now, the entry is saved in a file and, but it could be published in a queue

        """
        file_path = f"{os.path.join(self.document_local_path, self.document_local_folder)}/{file_name}"
        with open(file_path, "w") as f:
            f.write(content)
        logger.info(f"File {file_name} created in {file_path}")

    def full_text_search_retriever_service(self, query, start, rows, document_repository):
        """
        This method is used to retrieve the documents from the Catalog and generate the full text search entry
        """
        count = 0
        for result in self.retrieve_documents(query, start, rows):
            for record in result:

                item_id = record.ht_id
                logger.info(f"Processing document {item_id}")

                try:
                    self.generate_full_text_entry(item_id, record, document_repository)
                except Exception as e:
                    logger.error(f"Document {item_id} failed {e}")
                    continue
            count += len(result)
            logger.info(f"Total of processed items {count}")

    def generate_full_text_entry(self, item_id: str, record: catalog_metadata.CatalogItemMetadata,
                                 document_repository: str):

        logger.info(f"Generating document {item_id}")

        # Instantiate each document
        ht_document = HtDocument(document_id=item_id, document_repository=document_repository)

        logger.info(f"Checking path {ht_document.source_path}")

        # TODO: Temporal local for testing using a sample of files
        #  Checking if the file exist, otherwise go to the next
        if os.path.isfile(f"{ht_document.source_path}.zip"):
            logger.info(f"Processing item {ht_document.document_id}")
            try:
                entry = self.document_generator.make_full_text_search_document(ht_document, record)
            except Exception as e:
                raise e
            self.publish_document(file_name=f"{ht_document.namespace}{ht_document.file_name}_solr_full_text.xml",
                                  content=create_solr_string(entry))
        else:
            logger.info(f"{ht_document.document_id} does not exist")


def main():
    parser = argparse.ArgumentParser()
    init_args_obj = RetrieverServiceArguments(parser)

    if init_args_obj.query is None:
        logger.error("Error: `query` parameter required")
        sys.exit(1)

    document_indexer_service = FullTextSearchRetrieverService(init_args_obj.solr_api_catalog,
                                                              init_args_obj.document_generator,
                                                              init_args_obj.document_local_path,
                                                              init_args_obj.document_local_folder
                                                              )

    document_indexer_service.full_text_search_retriever_service(
        init_args_obj.query,
        init_args_obj.start,
        init_args_obj.rows,
        document_repository=init_args_obj.document_repository)


if __name__ == "__main__":
    main()
