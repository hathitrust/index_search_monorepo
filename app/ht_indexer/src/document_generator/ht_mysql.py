import os
import sys
import threading
from typing import Any
import time

from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import get_general_error_message
from mysql import connector

logger = get_ht_logger(name=__name__)

class HtMysql:

    # TODO: This class should be implemented on common utils package to be reused by other services

    _pool = None # Class variable to store the connection pool
    _lock = threading.Lock() # Lock for thread-safe pool creation

    def __init__(self, host: str = None, user: str = None, password: str = None, database: str = None,
                 pool_size: int = 5):
        """Initialize MySQL connection using the connection pooling"""
        if not HtMysql._pool:
            # Use the lock to ensure only one thread can execute the pool creation code at a time (double-checked locking pattern).
            with HtMysql._lock:
                if not HtMysql._pool:
                    HtMysql.create_connection_pool(host=host, user=user, password=password, database=database,
                                                   pool_size=pool_size)

    def query_mysql(self, query: str = None) -> list[Any] | None | list[dict[Any, Any]]:

        """Execute a query in MySQL and return the results as a list of dictionaries"""

        if not query:
            logger.error("Please pass the valid query")
            return []

        conn = None
        cursor = None
        try:
            conn = self.get_connection_from_pool()
            cursor = conn.cursor()
            cursor.execute(query)

            results = cursor.fetchall()

            list_docs = []
            for row in results:
                doc = {}
                for name, value in zip(cursor.description, row, strict=False):
                    doc.update({name[0]: value})
                list_docs.append(doc)
        except connector.Error as e:
            logger.error(f"MySQL Query Error: "
                         f"{get_general_error_message('DatabaseQuery', e)}")
            return []
        finally:
            if cursor:
                cursor.close() # Close the cursor
            if conn:
                conn.close() # Return the connection to the pool

        return list_docs

    @staticmethod
    def create_connection_pool(host: str = None, user: str = None, password: str = None, database: str = None,
                               pool_size: int = 5):
        """Create a connection pool for MySQL if doesn't exist"""

        if not all([host, user, password, database]):
            logger.error("Please pass the valid host, user, password and database")
            sys.exit(1)
        try:
            HtMysql._pool = connector.pooling.MySQLConnectionPool(pool_name="ht_mysql_pool",
                                                                        pool_size=pool_size,
                                                                        host=host,
                                                                        user=user,
                                                                        password=password,
                                                                        database=database)
            logger.info(f"MySQL connection pool created with size {pool_size}")
        except connector.Error as e:
            logger.error(f"MySQL Connection Pool Error: "
                         f"{get_general_error_message('DatabaseConnection', e)}")
            sys.exit(1)

    @staticmethod
    def get_connection_from_pool():
        """
        Retrieve a connection from the pool.
        """
        try:
            # Add timeout to prevent indefinite blocking when pool is exhausted
            timeout = 30  # 30 seconds timeout
            start_time = time.time()
            # Retry mechanism to handle temporary pool exhaustion - If pool is exhausted, it retries every 500ms
            # instead of failing immediately
            while True:
                try:
                    return HtMysql._pool.get_connection()
                except connector.PoolError as e:
                    # Logs warning when pool is temporarily exhausted and retries
                    if time.time() - start_time > timeout:
                        logger.error(f"Timeout getting connection from pool after {timeout}s: "
                                     f"{get_general_error_message('DatabaseConnection', e)}")
                        raise
                    logger.warning(f"Pool temporarily exhausted, retrying... ({e})")
                    time.sleep(0.5)  # Wait 500ms before retry
        except connector.Error as e:
            logger.error(f"Error getting connection from pool: "
                         f"{get_general_error_message('DatabaseConnection', e)}")
            sys.exit(1)

    def table_exists(self, table_name: str) -> bool|None:
        cursor = None
        conn = None
        try:
            conn = self.get_connection_from_pool()
            cursor = conn.cursor()
            cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
            result = cursor.fetchone()
            return result is not None
        except connector.Error as e:
            logger.error(f"Error checking if table exists: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def insert_batch(self, insert_query: str, batch_values: list):
        cursor = None
        conn = None
        try:
            conn = self.get_connection_from_pool()
            cursor = conn.cursor()
            cursor.executemany(insert_query, batch_values)
            conn.commit()
            logger.info(f"Inserted {len(batch_values)} records successfully.")
        except connector.Error as e:
            logger.error(f"Error inserting batch of records: {e}")
            conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def create_table(self, create_table_sql: str):
        cursor = None
        conn = None
        try:
            conn = self.get_connection_from_pool()
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            conn.commit()
            logger.info("Table created successfully")
        except connector.Error as e:
            logger.error(f"Failed to create table: {e}")
            conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def update_status(self, update_query: str, update_values: list[tuple[tuple[str, str]]]):
        """
        Update the status of a record in a table.
        :param update_query: The update query.
        :param update_values: The values to update.
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection_from_pool()
            cursor = conn.cursor()
            cursor.executemany(update_query, update_values)
            logger.info(f"Updated {cursor.rowcount} records successfully.")
            conn.commit()

        except connector.Error as e:
            logger.error(f"Error updating status: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    logger.error(f"Error during rollback: {rollback_error}")
        # Connection cleanup in case of error to ensure no connections are left hanging and preventing leaks
        # Ensure cursors and connections are closed properly
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception as cursor_error:
                    logger.error(f"Error closing cursor: {cursor_error}")
            if conn:
                try:
                    conn.close()
                except Exception as conn_error:
                    logger.error(f"Error closing connection: {conn_error}")

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
        host=mysql_host,
        user=mysql_user,
        password=mysql_pass,
        database=os.getenv("MYSQL_DATABASE", "ht"),
        pool_size=pool_size
    )

    logger.info("Access by default to `ht` Mysql database")

    return ht_mysql
