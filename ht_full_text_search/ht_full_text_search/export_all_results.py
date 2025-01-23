import json
import inspect
import os
import sys
from argparse import ArgumentParser

import requests
import yaml
from requests.auth import HTTPBasicAuth

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.insert(0, current_dir)

config_file_path = os.path.join(os.path.abspath(os.path.join(os.getcwd())),
                                           'config_files', 'full_text_search', 'config_query.yaml')

from config_search import default_solr_params, SOLR_URL

# This is a quick attempt to do a query to solr more or less as we issue it in
# production and to then export all results using the cursorMark results
# streaming functionality.

# This assumes the 'production' config with all shards available.

# Usage:
#
# poetry run python3 ht_full_text_search/export_all_results.py 'your query string'
#
# If you want to do a phrase query, be sure to surround it in double quotes, e.g.
# poetry run python3 ht_full_text_search/export_all_results.py '"a phrase"'

# TODO: ht_full_text_search should change to become the python library we use for quering our Solr clusters. Right now,
# the code is implemented to run queries only in the full text search cluster. We should have a more generic way to
# query any Solr cluster we have, including the catalog ones.
# We should have a way to configure the Solr cluster we want to query, the environment, the collection, etc.
# We should have a way to configure the fields we want to return in the query results
# We should have a way to configure the fields we want to use in the query
# We should have a way to configure the fields we want to use in the query to boost the results

# We should have generic classes to Search, make queries, filters and facets and print the query results.
# We should create specific classes (catalog => catalog-api, catalog-monitoring, fulltext => fulltext-api,
# fulltext-monitoring) children of the generic ones that have their own ways to make queries

# TODO: Implement the class to manage Solr query results.
# Specify the fields to show in the query result
# Specify if the Solr debug output will be show.Create our onw debug dictionary with fields we decide,
# e.g. QTime, status, shards, etc.
def process_results(item: dict) -> str:

    """ Prepare the dictionary with Solr results to be exported as JSON """

    return json.dumps({
        "id": item["id"],
        "author": item.get("author", []),
        "title": item.get("title", [])
    })


def solr_query_params(config_file=config_file_path, conf_query="ocr"):

    """ Prepare the Solr query parameters
    :param config_file: str, path to the config file
    :param conf_query: str, query configuration name
    :return: str, formatted Solr query parameters
    """

    with open(config_file, "r") as file:
        data = yaml.safe_load(file)[conf_query]

        params = {
            "pf": SolrExporter.create_boost_phrase_fields(data["pf"]),
            "qf": SolrExporter.create_boost_phrase_fields(data["qf"]),
            "mm": data["mm"],
            "tie": data["tie"]
        }
        return " ".join([f"{k}='{v}'" for k, v in params.items()])


def make_query(query):

    """ Prepare the Solr query string
        :param query: str, query string
        :return: str, formatted Solr query string
    """
    return f"{{!edismax {solr_query_params()}}} {query}"


class SolrExporter:

    def __init__(self, solr_url: str, env: str, user=None, password=None):

        """ Initialize the SolrExporter class
        :param solr_url: str, Solr URL
        :param env: str, environment. It could be dev or prod
        """

        self.solr_url = f"{solr_url}/query"
        self.environment = env
        self.headers = {"Content-Type": "application/json"}
        self.auth = HTTPBasicAuth(user, password) if user and password else None

    def send_query(self, params):

        """ Send the query to Solr
        :param params: dict, query parameters
        :return: response
        """

        # Use stream=True to avoid loading all the data in memory at once (useful for large responses)
        # In chunked transfer, the data stream is divided into a series of non-overlapping "chunks".

        response = requests.post(
            url=self.solr_url, params=params, headers=self.headers, stream=True,
            auth=self.auth
        )

        return response

    def run_cursor(self, query):

        """ Run the cursor to export all result
        The cursorMark parameter is used to keep track of the current position in the result set.
        :param query: str, query string
        :return: generator
        """

        params = default_solr_params(self.environment)
        params["cursorMark"] = "*"
        # TODO: Implement the feature to access to Solr debug using this python script
        params["debugQuery"] = "true"
        params["q"] = make_query(query)

        while True:
            results = self.send_query(params)  # send_query

            output = json.loads(results.content)

            for result in output['response']['docs']:
                yield process_results(result)
            if params["cursorMark"] != output["nextCursorMark"]:
                params["cursorMark"] = output["nextCursorMark"]
            else:
                break

    @staticmethod
    def create_boost_phrase_fields(query_fields):

        """ Create the boost phrase fields
        :param query_fields: list, list of field
        :return: str, formatted boost phrase fields
        """

        # phrase fields ==> Once the list of matching documents has been identified using the fq and qf parameters,
        # the pf parameter can be used to "boost" the score of documents in cases where all the terms
        # in the q parameter appear in close proximity.
        formatted_boosts = ["^".join(map(str, field)) for field in query_fields]
        return " ".join(formatted_boosts)

    def get_solr_status(self):

        """ Get the Solr status
        :return: response
        """
        response = requests.get(self.solr_url, auth=self.auth)
        return response


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))
    parser.add_argument("--solr_host", help="Solr host", default=None)
    parser.add_argument("--collection_name", help="Name of the collection", default=None)
    parser.add_argument('--query', help='Query string', required=True)

    args = parser.parse_args()

    # Receive as a parameter an specific solr url
    if args.solr_host:
        solr_url = f"{args.solr_host}/solr/{args.collection_name}"
    else:  # Use the default solr url, depending on the environment. If prod environment, use shards
        solr_url = SOLR_URL[args.env]
    solr_exporter = SolrExporter(solr_url, args.env,
                                 user=os.getenv("SOLR_USER"), password=os.getenv("SOLR_PASSWORD"))
    # '"good"'
    for x in solr_exporter.run_cursor(args.query):
        print(x)
