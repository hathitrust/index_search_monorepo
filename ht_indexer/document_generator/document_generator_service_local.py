import os
import json
import argparse

from document_generator.document_generator_service import DocumentGeneratorService
from ht_queue_service.queue_consumer import QueueConsumer
from indexer_config import DOCUMENT_LOCAL_PATH
from document_generator.generator_arguments import GeneratorServiceArguments

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class DocumentGeneratorServiceLocal(DocumentGeneratorService):
    def __init__(self, db_conn,
                 src_queue_consumer: QueueConsumer,
                 document_local_path: str = DOCUMENT_LOCAL_PATH,
                 document_repository: str = None,
                 document_local_folder: str = "indexing_data",
                 not_required_tgt_queue: bool = True):
        """
        This class is responsible to retrieve from the queue a message with metadata at item level and generates
        the full text search entry and publish the document in a local folder

        :param db_conn: Mysql connection
        :param src_queue_consumer: Connection of the queue to read the messages
        :param document_local_path: Path of the folder where the documents (.xml file to index) are stored.
        :param document_local_folder: Folder where the documents are stored
        :param document_repository: Parameter to know if the plain text of the items is in the local or remote repository
        """

        super().__init__(db_conn, src_queue_consumer=src_queue_consumer,
                         document_repository=document_repository,
                         not_required_tgt_queue=not_required_tgt_queue
                         )

        self.document_local_folder = document_local_folder
        self.document_local_path = document_local_path

        # Create the directory to load the JSON files if it does not exit
        try:
            if self.document_local_path:
                document_local_path = os.path.abspath(self.document_local_path)
            os.makedirs(os.path.join(document_local_path, document_local_folder))
        except FileExistsError:
            pass

    def publish_document(self, content: dict = None):
        """
        Right now, the entry is saved in a file and, but it could be published in a queue
        """
        file_name = content.get('id')

        file_path = f"{os.path.join(self.document_local_path, self.document_local_folder)}/{file_name}.json"
        with open(file_path, "w") as f:
            json.dump(content, f)
        logger.info(f"File {file_name} created in {file_path}")


def main():
    """ This script will process the remaining documents in the queue and generate the full-text search documents in
    a local computer. Each stage is process in sequence."""

    # 1. Retrieve the documents from the queue AND # 2. Generate the full text search entry AND
    # 3. Publish the document in a local folder

    parser = argparse.ArgumentParser()

    init_args_obj = GeneratorServiceArguments(parser)

    # Generate full-text search document in a local folder
    document_generator_service = DocumentGeneratorServiceLocal(init_args_obj.db_conn,
                                                               init_args_obj.src_queue_consumer,
                                                               document_local_path=init_args_obj.document_local_path,
                                                               document_repository=init_args_obj.document_repository,
                                                               document_local_folder="indexing_data",
                                                               not_required_tgt_queue=init_args_obj.not_required_tgt_queue)
    document_generator_service.generate_document()


if __name__ == "__main__":
    main()
