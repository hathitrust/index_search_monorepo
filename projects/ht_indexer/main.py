import argparse
import os

import uvicorn
from fastapi import FastAPI
from ht_indexer_api import HTSolrAPI

from base.ht_utils import get_ht_logger

logger = get_ht_logger(name=__name__)


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
        logger.info("Connecting with Solr server")

        global solr_api
        solr_user = os.getenv("SOLR_USER")
        solr_password = os.getenv("SOLR_PASSWORD")
        solr_api = HTSolrAPI(url=args.solr_url, user=solr_user, password=solr_password)

    @app.get("/ping")
    def check_solr():
        response = solr_api.get_solr_status()
        return {"status": response.status_code, "description": response.headers}

    @app.post("/solrIndexing/")
    def solr_indexing(path, list_documents: list = None):
        """Read an XML and feed into SOLR for indexing"""
        response = solr_api.index_documents_by_file(path, list_documents=list_documents)
        return {"status": response.status_code, "description": response.headers}

    uvicorn.run(app, host=args.host, port=int(args.port))


if __name__ == "__main__":
    main()
