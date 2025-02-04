import json
import os
import sys
import inspect
from argparse import ArgumentParser

from config_search import FULL_TEXT_SOLR_URL
from ht_full_text_search.ht_full_text_query import HTFullTextQuery
from ht_searcher.ht_searcher import HTSearcher
from typing import Text, List, Dict

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

"""
LS::Operation::Search ==> it contains all the logic about interleaved adn A/B tests
"""


class HTFullTextSearcher(HTSearcher):
    def __init__(
            self,
            solr_url: Text = None,
            ht_search_query: HTFullTextQuery = None,
            environment: str = "dev",
            user=None, password=None
    ):
        super().__init__(
            solr_url=solr_url,
            ht_search_query=ht_search_query,
            environment=environment,
            user=user,
            password=password
        )

    def solr_result_output(
            self, q_string: Text = None, fl: List = None, operator: Text = None, q_filter: bool = False,
            filter_dict: Dict = None):

        """With one query accumulate all the results"""

        list_docs = []
        result_explanation = []
        for response in self.solr_result_query_dict(q_string, fl, operator, q_filter, filter_dict):

            for record in response.get("response").get("docs"):
                list_docs.append(record)
            for key, value in response.get("debug").get("explain").items():
                result_explanation.append({key: value})

        return list_docs, result_explanation

    def retrieve_documents_from_file(self, q_string: Text = None, fl: List = None,
                                     operator: Text = None,
                                     q_filter: bool = False,
                                     list_ids: List = None, ):

        """
        This function create the Solr query using the ht_id from a list of ids
        :param list_ids: List of ids
        :param fl: Fields to return
        :param q_filter: If the query is using filter, then use config_facet_filters.yaml to create the fq parameter
        :param q_string: Query string
        :param operator: Operator, it could be, None (exact_match), "AND" (all these words) or "OR" (any of these words)
        :return:
        """

        # Processing long queries
        if len(list_ids) > 100:
            # processing the query in batches
            while list_ids:
                chunk, list_ids = list_ids[:100], list_ids[100:]

                list_docs, list_debug = self.solr_result_output(q_string=q_string, fl=fl, operator=operator, filter_dict={"id": chunk},
                    q_filter=q_filter
                )
                print(f"One batch of results {len(chunk)}")

                yield list_docs, list_debug

        # TODO implement the of AB test and interleave, Check the logic in the LS::Operation::Search.
        #  In previous versions of this repository you will find the logic to implement this feature (perl code
        #  transform to python code)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))
    parser.add_argument("--query_string", help="Query string", default="*:*")
    parser.add_argument(
        "--fl", help="Fields to return", default=["author", "id", "title", "score"]
    )
    parser.add_argument("--solr_url", help="Solr url", default=None)
    parser.add_argument("--operator", help="Operator", type=str) # Default value is None
    parser.add_argument(
        "--query_config", help="Type of query ocronly or all", default="all"
    )
    parser.add_argument(
        "--use_shards", help="If the query should include shards", default=False, action="store_true"
    )
    parser.add_argument(
        "--filter_path", help="Path of a JSON file used to filter Solr results", default=None
    )

    # input:
    args = parser.parse_args()

    # Receive as a parameter an specific solr url
    if args.solr_url:
        solr_url = args.solr_url
    else:  # Use the default solr url, depending on the environment. If prod environment, use shards
        solr_url = FULL_TEXT_SOLR_URL[args.env]

    solr_user = os.getenv("SOLR_USER")
    solr_password = os.getenv("SOLR_PASSWORD")

    query_string = args.query_string
    fl = args.fl

    # Create query object
    Q = HTFullTextQuery(config_query=args.query_config, config_facet_field="all")

    # Create a full text searcher object
    ht_full_search = HTFullTextSearcher(
        solr_url=solr_url, ht_search_query=Q, environment=args.env, user=solr_user, password=solr_password
    )

    filter_dict = {}
    q_filter = False

    if args.filter_path:

        # Generate filter dictionary from JSON file
        filter_json_file = open(args.filter_path, "r")
        filter_dict = json.loads(filter_json_file.read())
        q_filter = True

        total_found = 0

        list_ids = [doc_id['id'] for doc_id in filter_dict.get('response', {}).get('docs', []) if doc_id.get('id')]

        # Processing long queries
        for doc, debug_info in ht_full_search.retrieve_documents_from_file(q_string=query_string, fl=fl,
                                                                           operator=args.operator,
                                                                           q_filter=q_filter,
                                                                           list_ids=list_ids,
                                                                           ):
            print('**********************************')
            print(doc)
            print(debug_info)
    else:
        solr_output = ht_full_search.solr_result_output(q_string=query_string, fl=fl, operator=args.operator
        )
        print(f"Total found {len(solr_output)}")
        print(solr_output)
