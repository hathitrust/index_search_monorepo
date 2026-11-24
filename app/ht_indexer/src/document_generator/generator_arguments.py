import argparse
import sys

# root imports
from ht_queue_service.queue_producer import QueueProducer
from ht_queue_service.queue_settings import QueueSettings
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_mysql import HtMysql, get_mysql_conn

# utils
from ht_utils.ht_utils import get_general_error_message
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from . import generator_config_file_path

logger = get_ht_logger(name=__name__)


class GeneratorSourceQueueSettings(QueueSettings):
    model_config = SettingsConfigDict(
        env_prefix="RABBITMQ_GENERATOR_SRC_",
        yaml_file=generator_config_file_path / "generator_config.yml",
        yaml_config_section="src_queue",
    )


class GeneratorTargetQueueSettings(QueueSettings):
    model_config = SettingsConfigDict(
        env_prefix="RABBITMQ_GENERATOR_TGT_",
        yaml_file=generator_config_file_path / "generator_config.yml",
        yaml_config_section="tgt_queue",
    )


class GeneratorServiceArguments:
    def __init__(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--document_repository",
            help="Document source: 'pairtree' or 'local'.",
            choices=["pairtree", "local"],
            default="local",
        )

        # Path to the folder where the documents are stored. This parameter is useful for running the script locally
        parser.add_argument(
            "--document_local_path",
            help="Path of the folder where the documents (.xml file to index) are stored.",
            required=False,
            default=None,
        )

        parser.add_argument(
            "--tgt_local",
            action="store_true",
            help="Parameter to define the generated documents will be published in a queue."
            "By default is False, if the parameter is store, then is True and "
            "the documents will be stored in a local folder.",
        )

        self.args = parser.parse_args()

        try:
            self.src_queue_settings = GeneratorSourceQueueSettings()
            self.tgt_queue_settings = GeneratorTargetQueueSettings()
        except ValidationError as e:
            logger.error(f"Invalid queue configuration {e}")
            sys.exit(1)

        self.tgt_local: bool = self.args.tgt_local
        self.tgt_queue_producer: QueueProducer | None = None

        # MySql connection
        # TODO: Create the db connection pool when required by document_generator_service instead of here to shorten the
        #  startup time of the service
        self.db_conn = self.get_db_conn()

        if not self.tgt_local:
            self.tgt_queue_producer = GeneratorServiceArguments._make_producer(
                self.tgt_queue_settings
            )

        # Local output options
        self.document_repository: str = self.args.document_repository
        self.document_local_path: str | None = self.args.document_local_path

    def get_db_conn(self, pool_size: int = 1) -> HtMysql:
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
    def _make_producer(queue_settings: QueueSettings) -> QueueProducer:
        try:
            return QueueProducer(queue_settings)
        except Exception as e:
            logger.error(
                f"Queue connection required: {get_general_error_message('DocumentGeneratorService', e)}"
            )
            sys.exit(1)
