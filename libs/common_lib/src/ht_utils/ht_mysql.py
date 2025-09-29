import os
import sys
import threading
from typing import Any, Optional, List, Dict
from sqlalchemy import create_engine, text, exc
from sqlalchemy.engine import Engine
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import get_general_error_message

logger = get_ht_logger(name=__name__)

class HtMysql:
    _engine: Optional[Engine] = None # Class variable to store the SQLAlchemy engine
    _lock = threading.Lock() # Lock for thread-safe engine creation
    _engine_config = None # To store the configuration of the engine

    def __init__(self, host: str, user: str, password: str, database: str, pool_size: int = 5):
        """Initialize MySQL connection using SQLAlchemy engine with connection pooling"""
        config = (host, user, password, database, pool_size)
        # TODO: Consider adding more parameters like pool_timeout, pool_recycle, max_overflow to manage them
        # from Kubernetes config or environment variables
        # TODO: Check if we need to handle disconnects and retries here or SQLAlchemy handles is enough
        with HtMysql._lock:
            if HtMysql._engine is None:
                url = f"mysql+mysqlconnector://{user}:{password}@{host}/{database}"
                # This set up will automatically reconnect if the connection is lost
                HtMysql._engine = create_engine(
                    url,
                    pool_size=pool_size,
                    pool_pre_ping=True, # Check if connections are alive - test connection before using
                    pool_recycle=1800, # Recycle connections after 30 minutes - Avoid timeout
                    max_overflow=10, # Allow some extra connections
                )
                HtMysql._engine_config = config
                logger.info(f"SQLAlchemy engine created with pool size {pool_size}")
            elif HtMysql._engine_config != config:
                raise RuntimeError("Engine already created with different configuration.")

    def query_mysql(self, query: str, params: Optional[dict] = None) -> List[Dict[str, Any]]:

        """Execute a query in MySQL and return the results as a list of dictionaries
        :param query: The SQL query to execute
        :param params: Optional dictionary of parameters to bind to the query
        :return: List of dictionaries representing the query results
        """

        if not query:
            logger.error("Please pass the valid query")
            return []
        try:
            with HtMysql._engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                # Use row._mapping to retorn a RowMapping object that behaves like a dictionary
                rows = [dict(row._mapping) for row in result]
                return rows
        except exc.SQLAlchemyError as e:
            logger.error(f"MySQL Query Error: {get_general_error_message('DatabaseQuery', e)}")
            return []

    def table_exists(self, table_name: str) -> Optional[bool]:
        query = "SHOW TABLES LIKE :table"
        try:
            with HtMysql._engine.connect() as conn:
                result = conn.execute(text(query), {"table": table_name})
                return result.fetchone() is not None
        except exc.SQLAlchemyError as e:
            logger.error(f"Error checking if table exists: {e}")
            return None

    def insert_batch(self, insert_query: str, batch_values: List[dict]):
        try:
            with HtMysql._engine.begin() as conn:
                conn.execute(text(insert_query), batch_values)
                logger.info(f"Inserted {len(batch_values)} records successfully.")
        except exc.SQLAlchemyError as e:
            logger.error(f"Error inserting batch of records: {e}")

    def create_table(self, create_table_sql: str):
        try:
            with HtMysql._engine.begin() as conn:
                conn.execute(text(create_table_sql))
                logger.info("Table created successfully")
        except exc.SQLAlchemyError as e:
            logger.error(f"Failed to create table: {e}")

    def update_status(self, update_query: str, update_values: List[dict]):
        try:
            with HtMysql._engine.begin() as conn:
                conn.execute(text(update_query), update_values)
                logger.info(f"Updated {len(update_values)} records successfully.")
        except exc.SQLAlchemyError as e:
            logger.error(f"Error updating status: {e}")

def get_mysql_conn(pool_size: int = 1) -> HtMysql:
    # MySql connection
    try:
        mysql_host = os.getenv("MYSQL_HOST", "mysql-sdr")
        logger.info(f"Connected to MySql_Host: {mysql_host}")
    except KeyError:
        logger.error("Error: `MYSQL_HOST` environment variable required")
        sys.exit(1)

    try:
        mysql_user = os.getenv("MYSQL_USER", "mdp-lib")
        logger.info(f"Connected to MySql_User: {mysql_user}")
    except KeyError:
        logger.error("Error: `MYSQL_USER` environment variable required")
        sys.exit(1)

    try:
        mysql_pass = os.getenv("MYSQL_PASS", "mdp-lib")
    except KeyError:
        logger.error("Error: `MYSQL_PASS` environment variable required")
        sys.exit(1)

    ht_mysql = HtMysql(
        mysql_host,
        mysql_user,
        mysql_pass,
        os.getenv("MYSQL_DATABASE", "ht"),
        pool_size=pool_size
    )

    logger.info("Access by default to `ht` Mysql database")

    return ht_mysql
