import argparse
import os

from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse

import uvicorn
from fastapi import FastAPI

from config_search import SOLR_URL
from ht_full_text_search.export_all_results import SolrExporter

exporter_api = {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))

    args = parser.parse_args()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        Startup the API to index documents in Solr
        """
        print("Connecting with Solr server")

        exporter_api['obj'] = SolrExporter(SOLR_URL[args.env], args.env, user=os.getenv("SOLR_USER"),
                                           password=os.getenv("SOLR_PASSWORD"))
        yield
        # Add some logic here to close the connection
    app = FastAPI(title="HT_FullTextSearchAPI", description="Search phrases in Solr full text index", lifespan=lifespan)

    @app.get("/ping")
    def check_solr():
        """Check if the API is up"""
        response = exporter_api['obj'].get_solr_status()
        return {"status": response.status_code, "description": response.headers}

    @app.post("/query/")
    def solr_query_phrases(query):
        """
        Look for exact matches in the OCR text.
        :param query: phrase to search
        :return: JSON with the results
        """
        return StreamingResponse(exporter_api['obj'].run_cursor(query), media_type="application/json")

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
