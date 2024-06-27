import os, sys, inspect

# Full-text search config parameters
SOLR_URL = {
    "prod": "http://localhost:8081/solr/core-1y/",
    "dev": "http://localhost:8983/solr/#/core-x/" #"http://localhost:64108/solr/#/core-x/", #,
}

FULL_TEXT_SEARCH_SHARDS_X = """solr-sdr-search-1:8081/solr/core-1x,solr-sdr-search-2:8081/solr/core-2x,solr-sdr-search-3:8081/solr/core-3x,solr-sdr-search-4:8081/solr/core-4x,solr-sdr-search-5:8081/solr/core-5x,solr-sdr-search-6:8081/solr/core-6x,solr-sdr-search-7:8081/solr/core-7x,solr-sdr-search-8:8081/solr/core-8x,solr-sdr-search-9:8081/solr/core-9x,solr-sdr-search-10:8081/solr/core-10x,solr-sdr-search-11:8081/solr/core-11x,solr-sdr-search-12:8081/solr/core-12x"""

FULL_TEXT_SEARCH_SHARDS_Y = """solr-sdr-search-1:8081/solr/core-1y,solr-sdr-search-2:8081/solr/core-2y,solr-sdr-search-3:8081/solr/core-3y,solr-sdr-search-4:8081/solr/core-4y,solr-sdr-search-5:8081/solr/core-5y,solr-sdr-search-6:8081/solr/core-6y,solr-sdr-search-7:8081/solr/core-7y,solr-sdr-search-8:8081/solr/core-8y,solr-sdr-search-9:8081/solr/core-9y,solr-sdr-search-10:8081/solr/core-10y,solr-sdr-search-11:8081/solr/core-11y,solr-sdr-search-12:8081/solr/core-12y"""


currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.insert(0, currentdir)

QUERY_PARAMETER_CONFIG_FILE = "/".join(
    [currentdir, "config_files/full_text_search/config_query.yaml"]
)
FACET_FILTERS_CONFIG_FILE = "/".join(
    [currentdir, "config_files/full_text_search/config_facet_filters.yaml"]
)
