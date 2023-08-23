import logging

import mysql.connector
from mysql.connector import Connect


def create_mysql_conn(host: str = None, user: str = None, password: str = None, database: str = None):
    db_conn = None
    if all([host, user, password, database]):


        db_conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )

    else:
        logging.error('Please pass the valid host, user, password and database')
        exit()

    return db_conn

def query_mysql(db_conn: Connect = None, query: str = None):

    cursor = db_conn.cursor()
    cursor.execute(query)

    results = cursor.fetchall()


    list_docs = []
    for row in results:
        doc = {}
        for name, value in zip(cursor.description, row):
            doc.update({name[0]: value})
        list_docs.append(doc)
    return list_docs #[{name[0]: value} for row in results for name, value in zip(cursor.description, row)]


