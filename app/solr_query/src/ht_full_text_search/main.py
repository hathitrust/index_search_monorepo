import argparse
import os
import uvicorn
import yaml

from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from ht_search.config_files import config_files_path
from ht_search.config_files.solr_data_sample import SOLR_OUTPUT_SAMPLE
from ht_search.config_search import FULL_TEXT_SOLR_URL
from ht_search.export_all_results import SolrExporter
from ht_search.ht_query.ht_query import HTSearchQuery

from pydantic import BaseModel

from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import write_csv_and_get_path
from ht_utils.query_maker import build_fq_query

logger = get_ht_logger(name=__name__)

exporter_api = {}
CONFIG_DATA={}
QUERY_CONFIG_PATH = Path(config_files_path, 'full_text_search/config_query.yaml')

#Using for query endpoint
class SearchRequest(BaseModel):
    field: str = "ocr"  # Default to ocr"
    query: str
    file_type: str = "json"  # Default to JSON, can be "csv"

# Models for advanced search
class SearchCriteria(BaseModel):
    field: str  # Field type (title, author, etc.)
    query: str  # Search term
    match_type: str="all of these words"  # "all of these words", "any of these words", "this exact phrase"

#Using for Advance search endpoint
class AdvancedSearchRequest(BaseModel):
    criteria: List[SearchCriteria]
    field_operators: List[str]=[]  # "AND" or "OR" between fields
    file_type: str = "json"  # Output format
    start_year: str = ""
    end_year: str = ""
    in_year: str = ""
    languages : list = []
    formats : list = []
    location : str = ""


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
        logger.info("Connecting with Solr server")

        solr_url = FULL_TEXT_SOLR_URL[args.env]
        if args.solr_url:
            solr_url = args.solr_url
        exporter_api['obj'] = SolrExporter(solr_url, args.env, user=os.getenv("SOLR_USER"),
                                               password=os.getenv("SOLR_PASSWORD"))

        with open(QUERY_CONFIG_PATH, "r") as file:
            CONFIG_DATA['data'] = yaml.safe_load(file)
        logger.info("Advance search config loaded")
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
    async def solr_query_phrases(request: SearchRequest):
        """
        Look for exact matches in the OCR text.
        :param query: Phrase to search
        :return: JSON with the results
        """

        # TODO: run_cursor, should receive the query_string and the query_type (ocr or all).
        # When the API is started the config file is loaded in memory,
        # so the query type can be used to select the kind of query to run and the params dict is updated with the query
        # string.

        # query_config_file_path = Path(config_files_path, 'full_text_search/config_query.yaml')
        query_config_file_path = Path(config_files_path, 'full_text_search/adv_config_query.yaml')


        # Use StreamingResponse to stream the results because run_cursor output is a generator, so data
        # is not loaded into memory and is sent in chunks.
        # return StreamingResponse(result, media_type="application/json")
        return StreamingResponse(exporter_api['obj'].run_cursor(request.query, query_config_path=query_config_file_path,
                                                                conf_query=request.field),
                                                                media_type="application/json")

    @app.post("/search_results/")
    def solr_search_results():
        """
        Look for exact matches in the OCR text.
        :return: JSON with the results
        """

        return SOLR_OUTPUT_SAMPLE

    @app.post("/advanced_search/")
    async def advanced_search(request: AdvancedSearchRequest):
        """
        Advanced search using edismax query syntax with proper field and operator handling.
        """
        if not request.criteria:
            return {"error": "No search criteria provided"}

        fields, joined_query = HTSearchQuery.get_criteria_fields_query(request.criteria, request.field_operators, CONFIG_DATA["data"])

        filter_fields = {
            "date":{"start_year":request.start_year,"end_year":request.end_year,"in_year":request.in_year},
            "language":request.languages,
            "format":request.formats,
            "location":request.location
        }
        fq_formatted = build_fq_query(filter_fields, CONFIG_DATA["data"])

        data = exporter_api['obj'].run_cursor(
            joined_query,
            query_config_path=QUERY_CONFIG_PATH,
            conf_query=fields,fq_formatted=fq_formatted
        )
        if request.file_type.lower() == "csv":
            meta = write_csv_and_get_path(data,out_dir="./csv_files")
            return JSONResponse(meta)
        return StreamingResponse(data,media_type="application/json")


    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
