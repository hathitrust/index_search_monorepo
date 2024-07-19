import pandas as pd
import os
import pathlib

if __name__ == "__main__":
    list_queries = []
    string_queries = ["majority of the votes",
                      "chief justice",
                      "Natural history",
                      "S-350 anti-drone",
                      "Shell Recharge cybersecurity",
                      "Charge point software cybersecurity",
                      "Shell Recharge software cybersecurity",
                      "panama",
                      "Network Rail cybersecurity",
                      "National Grid cybersecurity",
                      "26th Regiment",
                      "wind farm operator cybersecurity",
                      "cell",
                      "Chile",
                      "Culture in History: Essays in Honor of Paul Radin",
                      "S-350 anti-satellite",
                      "Genealogy",
                      "natural history"]

    print(f"Total string queries {len(string_queries)}.")
    kind_query = ["AND", "OR", None]
    print(f"Total kind of queries: {len(kind_query)}")

    engines = ["solr6", "solr8"]

    # Generating the list of queries
    for input_query in string_queries:
        for type_query in ["ocronly"]:
            for op_type in kind_query:
                list_queries.append(
                    {
                        "query_fields": type_query,
                        "query_string": input_query,
                        "operator": op_type,
                    }
                )

    list_hits_results = []
    for engine in engines:
        # Hits counter
        # Expected number of queries to compare: total of kind_query * string_queries (3 * 17) = 51 to compare
        print(f"Expected comparison {len(string_queries) * len(kind_query)}")

        hits_dict = []

        for query in list_queries:
            df_A = None
            print("***************")
            print(query)

            a_path = f'{query["query_fields"]}_{query["query_string"]}_{query["operator"]}_{engine}.csv'
            if pathlib.Path(a_path).is_file():
                df_A = pd.read_csv("/".join([os.getcwd(), a_path]), sep="\t")

                total_hits = df_A.shape[0]

                hits_dict.append({'engine': engine,
                                  'query_string': query['query_string'],
                                  'operator': query['operator'],
                                    'total_hits': total_hits
                                  })

            else:
                print(f"File {a_path} does not exist")
                hits_dict.append({'engine': engine,
                                  'query_string': query['query_string'],
                                  'operator': query['operator'],
                                  'total_hits': 0
                                  })

        df_tmp = pd.DataFrame(hits_dict)
        list_hits_results.append(df_tmp)

    # Merge results
    df = list_hits_results[0].merge(list_hits_results[1], on=['query_string', 'operator'], suffixes=('_solr6', '_solr8'))
    df.to_csv(
        path_or_buf='solr6_y_solr8_hits_16908_documents.csv',
        index=False,
        sep="\t"
    )
