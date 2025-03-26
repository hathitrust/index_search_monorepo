from typing import Any
import mysql
from mysql.connector import pooling
import ht_utils.ht_utils
import sys

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class HtMysql:

    _pool = None # Class variable to store the connection pool

    def __init__(self, host: str = None, user: str = None, password: str = None, database: str = None,
                 pool_size: int = 5):
        """Initialize MySQL connection using the connection pooling"""
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
                for name, value in zip(cursor.description, row):
                    doc.update({name[0]: value})
                list_docs.append(doc)
        except mysql.connector.Error as e:
            logger.error(f"MySQL Query Error: "
                         f"{ht_utils.ht_utils.get_general_error_message('DatabaseQuery', e)}")
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
            HtMysql._pool = mysql.connector.pooling.MySQLConnectionPool(pool_name="ht_mysql_pool",
                                                                        pool_size=pool_size,
                                                                        host=host,
                                                                        user=user,
                                                                        password=password,
                                                                        database=database)
            logger.info(f"MySQL connection pool created with size {pool_size}")
        except mysql.connector.Error as e:
            logger.error(f"MySQL Connection Pool Error: "
                         f"{ht_utils.ht_utils.get_general_error_message('DatabaseConnection', e)}")
            sys.exit(1)

    @staticmethod
    def get_connection_from_pool():
        """
        Retrieve a connection from the pool.
        """
        try:
            return HtMysql._pool.get_connection()
        except mysql.connector.Error as e:
            logger.error(f"Error getting connection from pool: "
                         f"{ht_utils.ht_utils.get_general_error_message('DatabaseConnection', e)}")
            sys.exit(1)