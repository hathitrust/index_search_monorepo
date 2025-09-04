import sys
from typing import Optional

from config import config_queue_file_path
from ht_queue_service.queue_config import QueueConfig, QueueParams
from . import generator_config_file_path
# root imports
from ht_queue_service.queue_consumer import QueueConsumer
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

# utils
from ht_utils.ht_utils import get_general_error_message
from .ht_mysql import get_mysql_conn

logger = get_ht_logger(name=__name__)

class GeneratorServiceArguments:

    def __init__(self, parser):
        parser.add_argument(
            "--document_repository",
            help="Document source: 'pairtree' or 'local'.",
            choices=["pairtree", "local"],
            default="local",
        )

        # Path to the folder where the documents are stored. This parameter is useful for running the script locally
        parser.add_argument("--document_local_path",
                            help="Path of the folder where the documents (.xml file to index) are stored.",
                            required=False,
                            default=None
                            )

        parser.add_argument("--tgt_local",
                            action='store_true',
                            help="Parameter to define the generated documents will be published in a queue."
                                 "By default is False, if the parameter is store, then is True and "
                                 "the documents will be stored in a local folder."
                            )

        self.args = parser.parse_args()

        # MySql connection
        # TODO: Create the db connection pool when required by document_generator_service instead of here to shorten the
        #  startup time of the service
        self.db_conn = self.get_db_conn()

        # Queue configuration
        self.src_queue_config, self.tgt_queue_config = GeneratorServiceArguments._build_queue_configs()

        # Queue clients
        self.src_queue_consumer = GeneratorServiceArguments._make_consumer(self.src_queue_config.queue_params)

        self.tgt_local: bool = self.args.tgt_local
        self.tgt_queue_producer: Optional[QueueProducer] = None

        if not self.tgt_local:
            self.tgt_queue_producer = GeneratorServiceArguments._make_producer(self.tgt_queue_config.queue_params)

        # Local output options
        self.document_repository: str = self.args.document_repository
        self.document_local_path: Optional[str] = self.args.document_local_path

    def get_db_conn(self, pool_size: int = 1):
        """Create (once) and return a MySQL connection."""
        try:
            self.db_conn = get_mysql_conn(pool_size=pool_size)
        except Exception as e:
            logger.error(
                f"Failed to create MySQL connection: "
                f"{get_general_error_message('DocumentGeneratorService', e)}"
            )
            sys.exit(1)
        return self.db_conn

    @staticmethod
    def _build_queue_configs() -> tuple[QueueConfig, QueueConfig]:
        """
        Build and validate queue configuration from YAML resources, then
        construct source and target QueueConfig instances.
        """
        global_config = config_queue_file_path / "global_config.yml"
        app_config = generator_config_file_path / "generator_config.yml"

        if not global_config.is_file():
            logger.error(f"Queue config file {global_config} does not exist")
            sys.exit(1)
        if not app_config.is_file():
            logger.error(f"Queue config file {app_config} does not exist")
            sys.exit(1)

        try:
            src_queue_config = QueueConfig(global_config, app_config, config_key="src_queue")
            tgt_queue_config = QueueConfig(global_config, app_config, config_key="tgt_queue")
            return src_queue_config, tgt_queue_config
        except KeyError as e:
            logger.error(
                f"Invalid queue configuration: {get_general_error_message('DocumentGeneratorService', e)}"
            )
            sys.exit(1)
        except Exception as e:
            # Unexpected errors: include traceback
            logger.exception("Unexpected error creating QueueConfig")
            logger.error(
                f"Queue configuration error: {get_general_error_message('DocumentGeneratorService', e)}"
            )
            sys.exit(1)

    @staticmethod
    def _make_consumer(queue_params: QueueParams) -> QueueConsumer:
        try:
            return QueueConsumer(queue_params)
        except KeyError as e:
            logger.error(
                f"Missing environment variables: {get_general_error_message('DocumentGeneratorService', e)}"
            )
            sys.exit(1)
        except Exception as e:
            logger.error(
                f"Queue connection required: {get_general_error_message('DocumentGeneratorService', e)}"
            )
            sys.exit(1)

    @staticmethod
    def _make_producer(queue_params: QueueParams) -> QueueProducer:
        try:
            return QueueProducer(queue_params)
        except KeyError as e:
            logger.error(
                f"Missing environment variables: {get_general_error_message('DocumentGeneratorService', e)}"
            )
            sys.exit(1)
        except Exception as e:
            logger.error(
                f"Queue connection required: {get_general_error_message('DocumentGeneratorService', e)}"
            )
            sys.exit(1)
