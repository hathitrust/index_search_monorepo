import argparse
import os

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.responses import StreamingResponse

from main_test import SOLR_OUTPUT_SAMPLE

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ht_full_text_search.config_search import FULL_TEXT_SOLR_URL
from ht_full_text_search.export_all_results import SolrExporter
from ht_full_text_search.config_files import config_files_path

exporter_api = {}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))
    parser.add_argument("--solr_url", help="Solr url", default=None)

    args = parser.parse_args()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        Startup the API to index documents in Solr
        """
        print("Connecting with Solr server")

        solr_url = FULL_TEXT_SOLR_URL[args.env]
        if args.solr_url:
            solr_url = args.solr_url
        exporter_api['obj'] = SolrExporter(solr_url, args.env, user=os.getenv("SOLR_USER"),
                                               password=os.getenv("SOLR_PASSWORD"))
        yield

        # Add some logic here to close the connection
    app = FastAPI(title="HT_FullTextSearchAPI", description="Search phrases in Solr full text index", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware, # type: ignore
        allow_origins=["http://localhost"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],)

    @app.get("/ping")
    def check_solr():
        """Check if the API is up"""
        response = exporter_api['obj'].get_solr_status()
        return {"status": response.status_code, "description": response.headers}

    @app.post("/query/")
    def solr_query_phrases(query):
        """
        Look for exact matches in the OCR text.
        :param query: Phrase to search
        :return: JSON with the results
        """

        # TODO: run_cursor, should receive the query_string and the query_type (ocr or all).
        # When the API is started the config file is loaded in memory,
        # so the query type can be used to select the kind of query to run and the params dict is updated with the query
        # string.

        query_config_file_path = Path(config_files_path, 'full_text_search/config_query.yaml')

        # Use StreamingResponse to stream the results because run_cursor output is a generator, so data
        # is not loaded into memory and is sent in chunks.
        # return StreamingResponse(result, media_type="application/json")
        return StreamingResponse(exporter_api['obj'].run_cursor(query, query_config_path=query_config_file_path,
                                                                conf_query="ocr"), media_type="application/json")

    @app.post("/search_results/")
    def solr_search_results():
        """
        Look for exact matches in the OCR text.
        :return: JSON with the results
        """

        return SOLR_OUTPUT_SAMPLE

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
