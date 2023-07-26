from ht_indexer_api.ht_indexer_api import HTSolrAPI
from fastapi import FastAPI
import uvicorn
import logging
import asyncio

import nest_asyncio

nest_asyncio.apply()

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

uvicorn.run(app, host='0.0.0.0', port=8081)

#if __name__ == '__main__':

