import mysql.connector

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class HtMysql:

    def __init__(self, host: str = None, user: str = None, password: str = None, database: str = None):
        self.db_conn = HtMysql.create_mysql_conn(host=host, user=user, password=password, database=database)

    @staticmethod
    def create_mysql_conn(host: str = None, user: str = None, password: str = None, database: str = None):
        if not all([host, user, password, database]):
            logger.error("Please pass the valid host, user, password and database")
            exit()
        return mysql.connector.connect(host=host, user=user, password=password, database=database)

    def query_mysql(self, query: str = None) -> list:
        cursor = self.db_conn.cursor()
        cursor.execute(query)

        results = cursor.fetchall()

        list_docs = []
        for row in results:
            doc = {}
            for name, value in zip(cursor.description, row):
                doc.update({name[0]: value})
            list_docs.append(doc)

        return list_docs  # [{name[0]: value} for row in results for name, value in zip(cursor.description, row)]
