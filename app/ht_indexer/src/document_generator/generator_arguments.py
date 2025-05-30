import os
import sys

# root imports
from ht_queue_service.queue_consumer import QueueConsumer
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_mysql import get_mysql_conn

# utils
from ht_utils.ht_utils import get_general_error_message

logger = get_ht_logger(name=__name__)

class GeneratorServiceArguments:

    def __init__(self, parser):
        parser.add_argument("--document_repository",
                            help="Could be pairtree or local", default="local"
                            )

        # Path to the folder where the documents are stored. This parameter is useful for running the script locally
        parser.add_argument("--document_local_path",
                            help="Path of the folder where the documents (.xml file to index) are stored.",
                            required=False,
                            default=None
                            )

        parser.add_argument("--not_required_tgt_queue",
                            action='store_true',
                            help="Parameter to define the generated documents will be publish in a queue."
                                 "If the parameter is set to False, the documents will be stored in a local folder.",
                            )

        self.args = parser.parse_args()

        # MySql connection
        self.db_conn = get_mysql_conn(pool_size=1)

        try:
            self.src_queue_consumer = QueueConsumer(os.environ["SRC_QUEUE_USER"],
                                                    os.environ["SRC_QUEUE_PASS"],
                                                    os.environ["SRC_QUEUE_HOST"],
                                                    os.environ["SRC_QUEUE_NAME"],
                                                    requeue_message=False,
                                                    batch_size=1)
        except KeyError as e:
            logger.error(f"Environment variables required: "
                         f"{get_general_error_message('DocumentGeneratorService', e)}")

            sys.exit(1)
        except Exception as e:
            logger.error(f"Queue connection required: "
                         f"{get_general_error_message('DocumentGeneratorService', e)}")
            sys.exit(1)

        # Publish documents in a queue or local folder
        self.not_required_tgt_queue = self.args.not_required_tgt_queue

        if not self.args.not_required_tgt_queue:
            try:
                self.tgt_queue_producer = QueueProducer(os.environ["TGT_QUEUE_USER"],
                                                        os.environ["TGT_QUEUE_PASS"],
                                                        os.environ["TGT_QUEUE_HOST"],
                                                        os.environ["TGT_QUEUE_NAME"],
                                                        batch_size=1)
            except KeyError as e:
                logger.error(f"Environment variables required: "
                             f"{get_general_error_message('DocumentGeneratorService', e)}")

                sys.exit(1)
            except Exception as e:
                logger.error(f"Queue connection required: "
                             f"{get_general_error_message('DocumentGeneratorService', e)}")
                sys.exit(1)

        # Variables used if the documents are stored in a local folder
        self.document_repository = self.args.document_repository
        self.document_local_path = self.args.document_local_path
