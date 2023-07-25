import os
from pathlib import Path

import requests
from fastapi import FastAPI
import uvicorn

from typing import Text, Dict
import logging
import json
import glob


class HTSolrAPI():

    def __init__(self, host: Text = 'localhost', port: int = 8983):

        self.url = f'http://{host}:{port}/solr/#/core-x/'

    def get_solr_status(self):
        response = requests.get(self.url)
        return response

    def index_document(self, path: Text):

        """Read an XML and feed into SOLR for indexing"""
        data_path = Path(f"{os.path.dirname(__file__)}/{path}")
        list_documents = glob.glob(f"{data_path}/*.xml")
        for doc in list_documents:
            doc = doc.replace(" ", "+")
            logging.info(f'Indexing {doc}')
            with open(doc, 'rb') as xml_file:
                data_dict = xml_file.read()

                response = requests.post("http://localhost:8983/solr/core-x/update/?commit=true",
                                         headers={"Content-Type": "application/xml"},
                                         data=data_dict,
                                         params={'commit': 'true', }
                                         )

                return response

    def get_documents(self, query: Dict = None, response_format: Text = 'json'):

        if query:

            data_query = f'query={json.dumps(query)}&wt={response_format}'
        else:
            data_query = ''
        response = requests.get(f"{self.url}query",
                                headers={"Content-Type": "x-www-form-urlencoded"},
                                data=data_query)
        return response


def main():
    app = FastAPI(title='HTSolrAPI', description='Indexing XML files in Solr server')
    host = 'localhost'
    port = 8983

    @app.on_event("startup")
    def solr_startup():
        """
        Startup the API to index documents in Solr
        """
        logging.info('Connecting with Solr server')

        global solr_api
        solr_api = HTSolrAPI(host=host, port=port)

    @app.get("/ping")
    def check_solr():

        response = solr_api.get_solr_status()
        return {'status': response.status_code,
                'description': response.headers}

    @app.post("/solrIndexing/")
    def solr_indexing(path):
        """Read an XML and feed into SOLR for indexing"""
        response = solr_api.index_document(path)
        return {'status': response.status_code,
                        'description': response.headers}

    @app.get('/solrQuery')
    def solr_query_id():
        return 0

    uvicorn.run(app, host='localhost', port=8081)

if __name__ == "__main__":
    main()
