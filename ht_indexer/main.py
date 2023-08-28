import argparse
import logging

import uvicorn
from fastapi import FastAPI

from ht_indexer_api.ht_indexer_api import HTSolrAPI


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host", help="HT indexer API host", required=True, default="0.0.0.0"
    )
    parser.add_argument(
        "--port", help="HT indexer API port", required=True, default=8081
    )
    # If you run main script from poetry/python solr_host = localhost
    # If you run main script from docker solr_host = host.docker.internal
    parser.add_argument(
        "--solr_url",
        help="",
        required=True,
        default="http://localhost:8983/solr/#/core-x/",
    )
    args = parser.parse_args()
    app = FastAPI(title="HTSolrAPI", description="Indexing XML files in Solr server")

    @app.on_event("startup")
    def solr_startup():
        """
        Startup the API to index documents in Solr
        """
        logging.info("Connecting with Solr server")

        global solr_api
        solr_api = HTSolrAPI(url=args.solr_url)

    @app.get("/ping")
    def check_solr():
        response = solr_api.get_solr_status()
        return {"status": response.status_code, "description": response.headers}

    @app.post("/solrIndexing/")
    def solr_indexing(path):
        """Read an XML and feed into SOLR for indexing"""
        response = solr_api.index_document(path)
        return {"status": response.status_code, "description": response.headers}

    @app.post("/solrQuery/")
    def solr_query_id(query):
        response = solr_api.get_documents(query)
        return {"status": response.status_code, "description": response.headers}

    uvicorn.run(app, host=args.host, port=int(args.port))


if __name__ == "__main__":
    main()
