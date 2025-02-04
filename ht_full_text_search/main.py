import argparse
import sys
import os
import inspect

from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse

import uvicorn
from fastapi import FastAPI

from config_search import FULL_TEXT_SOLR_URL
from ht_full_text_search.export_all_results import SolrExporter

exporter_api = {}

# Add the parent directory ~/ht_full_text_search into the PYTHONPATH.
current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
#parent = os.path.dirname(current)
sys.path.insert(0, current)

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

        if args.solr_url:
            exporter_api['obj'] = SolrExporter(args.solr_url, args.env, user=os.getenv("SOLR_USER"),
                                               password=os.getenv("SOLR_PASSWORD"))
        else:
            exporter_api['obj'] = SolrExporter(FULL_TEXT_SOLR_URL[args.env], args.env, user=os.getenv("SOLR_USER"),
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

        # TODO: run_cursor, should receive the query_string and the query_type (ocr or all).
        # When the API is started the config file is loaded in memory,
        # so the query type can be used to select the kind of query to run and the params dict is updated with the query
        # string.

        query_config_file_path = os.path.join(os.path.abspath(os.path.join(current)),
                                              'config_files', 'full_text_search', 'config_query.yaml')

        return StreamingResponse(exporter_api['obj'].run_cursor(query, query_config_path=query_config_file_path,
                                                                conf_query="ocr"), media_type="application/json")

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
