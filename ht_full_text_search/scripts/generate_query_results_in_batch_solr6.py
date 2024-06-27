
import pandas as pd
from ht_full_text_search.ht_full_text_query import HTFullTextQuery
from ht_full_text_search.ht_full_text_searcher import HTFullTextSearcher
from argparse import ArgumentParser
import os
from config_search import SOLR_URL, FULL_TEXT_SEARCH_SHARDS
import json

def clean_up_score_string(score_string):
    return score_string.strip("\n").strip("")


def create_doc_score_dataframe(solr_output_explaination):
    doc_score_list = {
        doc: clean_up_score_string(solr_output_explaination[doc].split("=")[0])
        for doc in solr_output["debug"]["explain"]
    }

    return doc_score_list


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))
    parser.add_argument("--solr_url", help="Solr url", default=None)
    parser.add_argument(
        "--fl", help="Fields to return", default=["author", "id", "title", "score"]
    )
    parser.add_argument(
        "--use_shards", help="If the query should include shards", default=False, action="store_true"
    )
    parser.add_argument(
        "--filter_path", help="Path of a JSON file used to filter Solr results", default=None
    )

    args = parser.parse_args()

    # Receive as a parameter an specific solr url
    if args.solr_url:
        solr_url = args.solr_url
    else:  # Use the default solr url, depending on the environment. If prod environment, use shards
        solr_url = SOLR_URL[args.env]

    fl = args.fl
    use_shards = False

    if args.env == "prod":
        use_shards = FULL_TEXT_SEARCH_SHARDS
    else:
        use_shards = args.use_shards  # By default is False

    list_queries = []
    # Generating the list of queries
    for input_query in [
        #"majority of the votes",
        #"chief justice",
        #"majority of the votes",
        #"chief justice",
        #"Natural history",
        ##"S-350 anti-drone",
        #"Shell Recharge cybersecurity",
        #"Charge point software cybersecurity",
        #"Shell Recharge software cybersecurity",
        #"panama",
        #"Network Rail cybersecurity",
        #"National Grid cybersecurity",
        #"26th Regiment",
        #"wind farm operator cybersecurity",
        #"cell",
        #"Chile",
        #"Culture in History: Essays in Honor of Paul Radin",
        #"S-350 anti-satellite",
        #"Genealogy"
        "natural history"
    ]:
        for type_query in ["ocronly"]: #, "all"
            for op_type in ["AND", "OR", None]:
                list_queries.append(
                    {
                        "query_fields": type_query,
                        "query_string": input_query,
                        "operator": op_type
                    }
                )

    for query in list_queries:

        df = pd.DataFrame(columns=args.fl)

        df_list_results = []

        fl = ["author", "id", "title"]
        print(f"Solr query {query['query_string']} with operator {query['operator']}")

        # Create query object
        Q = HTFullTextQuery(config_query=query['query_fields'])

        ht_full_search = HTFullTextSearcher(engine_uri=solr_url, ht_search_query=Q, use_shards=use_shards)

        total_found = 0

        if args.filter_path is None:
            solr_output = ht_full_search.solr6_result_curl_command(
                url=solr_url,
                str_query=query["query_string"],
                fl=fl,
                operator=query["operator"]
            )

            total_found += solr_output["response"]["numFound"]

            # Empty results
            if solr_output["response"]["numFound"] == 0:
                print(f'No results found for query {query["query_string"]}')
                continue

            df = pd.DataFrame(solr_output["response"]["docs"])

            #df_tmp = pd.DataFrame(solr_output["response"]["docs"])
            # Extract the score for each document
            doc_score_dict = create_doc_score_dataframe(solr_output["debug"]["explain"])
            df["score"] = df["id"].map(doc_score_dict)

            #df = pd.concat([df, df_tmp])
            #df_list_results.append(df_tmp)

        else:
            # Generate filter dictionary from JSON file
            filter_json_file = open(args.filter_path, "r")
            filter_dict = json.loads(filter_json_file.read())
            query_filter = True

            list_ids = [id['id'] for id in filter_dict.get('response', {}).get('docs', []) if id.get('id')]
            #list_ids = list_ids[0:101]
            print(f"Total of ids to process {len(list_ids)}")

            # Processing long queries
            if len(list_ids) > 100:
                # processing the query in batches
                while list_ids:
                    chunk, list_ids = list_ids[:100], list_ids[100:]

                    solr_output = ht_full_search.solr6_result_curl_command(
                        url=solr_url,
                        str_query=query["query_string"],
                        fl=fl,
                        operator=query["operator"],
                        list_filters=chunk
                    )

                    print(f"One batch of results {len(chunk)}")

                    total_found += solr_output["response"]["numFound"]

                    #Empty results
                    if solr_output["response"]["numFound"] == 0:
                        print(f'No results found for query {query["query_string"]}')
                        continue

                    df_tmp = pd.DataFrame(solr_output["response"]["docs"])

                    df_list_results.append(df_tmp)
                    #Extract the score for each document
                    #doc_score_dict = create_doc_score_dataframe(solr_output["debug"]["explain"])

                    #df_tmp["score"] = df_tmp["id"].map(doc_score_dict)

                    #df = pd.concat([df, df_tmp])

        print(f"Total found {total_found}")

        if df_list_results:
            df = pd.concat(df_list_results)

        df.to_csv(
            path_or_buf=f'{query["query_fields"]}_{query["query_string"]}_{query["operator"]}_solr6.csv',
            index=False,
            sep="\t"
        )
