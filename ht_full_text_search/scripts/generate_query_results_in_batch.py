import json
import os
import sys
from argparse import ArgumentParser

import pandas as pd

from config_search import FULL_TEXT_SOLR_URL
from ht_full_text_search.ht_full_text_query import HTFullTextQuery
from ht_full_text_search.ht_full_text_searcher import HTFullTextSearcher


def comma_separated_list(arg):
    return arg.split(",")


def clean_up_score_string(score_string):
    return score_string.strip("\n").strip("")


def create_doc_score_dataframe(solr_output_explanation):
    doc_score_dict = {}
    for doc in solr_output_explanation:
        for key, value in doc.items():
            doc_score_dict.update({'id': doc[key],
                                   'score': clean_up_score_string(value.split("=")[0].strip())})

    return doc_score_dict


def get_solr_results_without_filter_by_id(ht_full_search_obj: HTFullTextSearcher,
                                          query: dict, fl: list):
    """
    Get the results from Sol without filter it by id
    :param ht_full_search_obj: Search object
    :param query: query object
    :param fl: Fields to return
    :return:
    """

    list_docs = []
    total_found = 0

    for response in ht_full_search_obj.solr_result_query_dict(
            query_string=query["query_string"],
            fl=fl,
            operator=query["operator"]
    ):
        total_found += response.get("response").get("numFound")
        for record in response.get("response").get("docs"):
            list_docs.append(record)

    return total_found, list_docs


def get_list_phrases(file_path: str) -> list:
    if not os.path.isfile(file_path):
        print(f"File {file_path} not found")
        sys.exit(1)
    with open(file_path) as f:
        list_phrases = f.read().splitlines()

    return list_phrases


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))
    parser.add_argument("--solr_url", help="Solr url", default=None)
    parser.add_argument(
        "--fl", help="Fields to return", default=["author", "id", "title", "score"]
    )
    parser.add_argument(
        "--filter_path", help="Path of a JSON file used to filter Solr results", default=None
    )
    parser.add_argument(
        "--query_config", help="Type of query ocronly or/and all", default=["ocronly"],
        type=comma_separated_list)
    parser.add_argument("--list_phrase_file", help="TXT file containing the list of phrase to search",
                        default='')

    args = parser.parse_args()

    # Receive as a parameter an specific solr url
    if args.solr_url:
        solr_url = args.solr_url
    else:  # Use the default solr url, depending on the environment. If prod environment, use shards
        solr_url = FULL_TEXT_SOLR_URL[args.env]

    solr_user = os.getenv("SOLR_USER")
    solr_password = os.getenv("SOLR_PASSWORD")

    fl = args.fl
    use_shards = False  # By default is False

    list_queries = []

    list_phrases = get_list_phrases(args.list_phrase_file)

    # Generating the list of queries
    for input_query in list_phrases:
        for type_query in args.query_config:  # "ocronly", "all"
            for op_type in ["AND", "OR", None]:
                list_queries.append(
                    {
                        "query_fields": type_query,
                        "query_string": input_query,
                        "operator": op_type
                    }
                )

    for query in list_queries:

        fl = args.fl  # ["author", "id", "title"]

        # Create empty dataframe with the columns to be returned
        df = pd.DataFrame(columns=args.fl)

        print(f"Solr query {query['query_string']} with operator {query['operator']}")

        # Create query object
        Q = HTFullTextQuery(config_query=query['query_fields'])

        # Create the search object
        ht_full_search = HTFullTextSearcher(solr_url=solr_url, ht_search_query=Q, environment=args.env,
                                            user=solr_user, password=solr_password)

        total_found = 0

        if args.filter_path is None:
            # Get the results from Sol without filter it by id
            docs_found, list_docs = get_solr_results_without_filter_by_id(
                ht_full_search_obj=ht_full_search,
                query=query,
                fl=args.fl
            )

            total_found += docs_found

            # Empty results
            if docs_found == 0:
                print(f'No results found for query {query["query_string"]}')
                continue

            df = pd.DataFrame(list_docs)

            # Extract the score for each document
            # doc_score_dict = create_doc_score_dataframe(solr_output["debug"]["explain"])
            # df["score"] = df["id"].map(doc_score_dict)

        else:
            # Generate filter dictionary from JSON file
            filter_json_file = open(args.filter_path, "r")
            filter_dict = json.loads(filter_json_file.read())
            query_filter = True

            list_ids = [doc_id['id'] for doc_id in filter_dict.get('response', {}).get('docs', []) if doc_id.get('id')]

            print(f"Total of ids to process {len(list_ids)}")

            list_df_results = []
            # Processing long queries
            for doc, debug_info in ht_full_search.retrieve_documents_from_file(q_string=query["query_string"],
                                                                               fl=fl,
                                                                               operator=query["operator"],
                                                                               q_filter=query_filter,
                                                                               list_ids=list_ids):

                # Empty results
                if len(doc) == 0:
                    print(f'No results found for query {query["query_string"]}')
                    continue

                df_tmp = pd.DataFrame(doc)

                list_df_results.append(df_tmp)

            df = pd.concat(list_df_results)

        print(f"Total found {total_found}")

        # Save the results in a CSV files
        main_path = f'{os.getcwd()}/scripts/query_results'

        if not os.path.exists(main_path):
            os.makedirs(main_path)

        df.to_csv(
            path_or_buf=f'{main_path}/{query["query_fields"]}_{query["query_string"]}_{query["operator"]}_{args.env}.csv',
            index=False,
            sep="\t"
        )
