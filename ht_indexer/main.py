from ht_indexer_api.ht_indexer_api import HTSolrAPI
from fastapi import FastAPI
import uvicorn
import logging
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', help='HT indexer API host', required=True, default='0.0.0.0')
    parser.add_argument('--port', help='HT indexer API port', required=True, default=8081)
    # If you run main script from poetry/python solr_host = localhost
    # If you run main script from docker solr_host = host.docker.internal
    parser.add_argument('--solr_host', help='Solr server host', required=True, default='localhost')
    parser.add_argument('--solr_port', help='Solr server post', required=True, default=8983)
    args = parser.parse_args()
    app = FastAPI(title='HTSolrAPI', description='Indexing XML files in Solr server')

    @app.on_event("startup")
    def solr_startup():
        """
        Startup the API to index documents in Solr
        """
        logging.info('Connecting with Solr server')

        global solr_api
        solr_api = HTSolrAPI(host=args.solr_host, port=int(args.solr_port))

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

    uvicorn.run(app, host=args.host, port=int(args.port))


if __name__ == "__main__":
    main()
