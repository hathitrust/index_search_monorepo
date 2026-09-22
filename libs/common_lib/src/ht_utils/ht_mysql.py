import os
import threading
from typing import Any

from sqlalchemy import create_engine, exc, text
from sqlalchemy.engine import Engine

from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import get_general_error_message

logger = get_ht_logger(name=__name__)


class MissingMysqlConfigError(RuntimeError):
    """Raised when a required MySQL credential env var is missing.

    MYSQL_USER/MYSQL_PASS must be supplied explicitly rather than silently
    defaulted. A missing credential should fail loudly at startup, not connect
    as a guessed identity and surface as silent query failures later.
    """


class HtMysql:
    _engine: Engine | None = None  # Class variable to store the SQLAlchemy engine
    _lock = threading.Lock()  # Lock for thread-safe engine creation
    _engine_config: tuple[str, str, str, str, int] | None = None  # Configuration of the engine

    def __init__(self, host: str, user: str, password: str, database: str, pool_size: int = 5):
        """Initialize MySQL connection using SQLAlchemy engine with connection pooling.

        Opens and discards one connection to check if a bad credential or an
        unreachable host were provided, so it raises immediately here, instead of waiting for the the first
        service quering MySQL.
        """
        config = (host, user, password, database, pool_size)
        # TODO: Consider adding more parameters like pool_timeout, pool_recycle, max_overflow to manage them
        # from Kubernetes config or environment variables
        # TODO: Check if we need to handle disconnects and retries here or SQLAlchemy handles is enough
        with HtMysql._lock:
            if HtMysql._engine is None:
                url = f"mysql+mysqlconnector://{user}:{password}@{host}/{database}"
                # This set up will automatically reconnect if the connection is lost
                engine = create_engine(
                    url,
                    pool_size=pool_size,
                    pool_pre_ping=True,  # Check if connections are alive - test connection before using
                    pool_recycle=1800,  # Recycle connections after 30 minutes - Avoid timeout
                    max_overflow=10,  # Allow some extra connections
                )
                try:
                    with engine.connect():
                        pass
                except exc.SQLAlchemyError as e:
                    logger.error(
                        f"Unable to connect to MySQL: {get_general_error_message('DatabaseConnection', e)}"
                    )
                    raise
                HtMysql._engine = engine
                HtMysql._engine_config = config
                logger.info(f"SQLAlchemy engine created with pool size {pool_size}")
            elif HtMysql._engine_config != config:
                raise RuntimeError("Engine already created with different configuration.")

    @classmethod
    def _get_engine(cls) -> Engine:
        if cls._engine is None:
            raise RuntimeError("HtMysql engine not initialized")
        return cls._engine

    def query_mysql(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a query in MySQL and return the results as a list of dictionaries
        :param query: The SQL query to execute
        :param params: Optional dictionary of parameters to bind to the query
        :return: List of dictionaries representing the query results
        """

        if not query:
            logger.error("Please pass the valid query")
            return []
        try:
            with self._get_engine().connect() as conn:
                result = conn.execute(text(query), params or {})
                # Use row._mapping to retorn a RowMapping object that behaves like a dictionary
                rows = [dict(row._mapping) for row in result]
                return rows
        except exc.SQLAlchemyError as e:
            logger.error(f"MySQL Query Error: {get_general_error_message('DatabaseQuery', e)}")
            return []

    def table_exists(self, table_name: str) -> bool | None:
        query = "SHOW TABLES LIKE :table"
        try:
            with self._get_engine().connect() as conn:
                result = conn.execute(text(query), {"table": table_name})
                return result.fetchone() is not None
        except exc.SQLAlchemyError as e:
            logger.error(f"Error checking if table exists: {e}")
            return None

    def insert_batch(self, insert_query: str, batch_values: list[dict[str, Any]]) -> None:
        try:
            with self._get_engine().begin() as conn:
                conn.execute(text(insert_query), batch_values)
                logger.info(f"Inserted {len(batch_values)} records successfully.")
        except exc.SQLAlchemyError as e:
            logger.error(f"Error inserting batch of records: {e}")

    def create_table(self, create_table_sql: str) -> None:
        try:
            with self._get_engine().begin() as conn:
                conn.execute(text(create_table_sql))
                logger.info("Table created successfully")
        except exc.SQLAlchemyError as e:
            logger.error(f"Failed to create table: {e}")

    def update_status(self, update_query: str, update_values: list[dict[str, Any]]) -> None:
        try:
            with self._get_engine().begin() as conn:
                conn.execute(text(update_query), update_values)
                logger.info(f"Updated {len(update_values)} records successfully.")
        except exc.SQLAlchemyError as e:
            logger.error(f"Error updating status: {e}")


def _require_env(name: str) -> str:
    """Return the env var value, or raise MissingMysqlConfigError if unset/empty.

    :param name: Name of the environment variable to retrieve
    :return: Value of the environment variable
    :raises MissingMysqlConfigError: If the environment variable is not set or empty
    """
    value = os.getenv(name)
    if not value:
        logger.error(f"Error: `{name}` environment variable required")
        raise MissingMysqlConfigError(f"`{name}` environment variable required")
    return value


def get_mysql_conn(pool_size: int = 1) -> HtMysql:
    """MYSQL_HOST/MYSQL_DATABASE are not secrets, so if they are not provides, it will initiallice to default.

    MYSQL_USER/MYSQL_PASS are credentials: so, the application will fail fast if there are not provided. We don't want to silently
    connect as default to a guessed identity.

    :param pool_size: Number of connections in the pool
    :return: HtMysql instance
    """
    mysql_host = os.getenv("MYSQL_HOST", "mysql-sdr")
    mysql_database = os.getenv("MYSQL_DATABASE", "ht")
    mysql_user = _require_env("MYSQL_USER")
    mysql_pass = _require_env("MYSQL_PASS")

    logger.info(f"Connecting to MySql_Host: {mysql_host} database: {mysql_database}")

    ht_mysql = HtMysql(mysql_host, mysql_user, mysql_pass, mysql_database, pool_size=pool_size)

    logger.info(f"Connected to MySql database `{mysql_database}`")

    return ht_mysql
