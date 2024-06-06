
import pandas as pd
from ht_full_text_search.ht_full_text_query import HTFullTextQuery
from ht_full_text_search.ht_full_text_searcher import HTFullTextSearcher


def clean_up_score_string(score_string):
    return score_string.strip("\n").strip("")


def create_doc_score_dataframe(solr_output_explaination):
    doc_score_list = {
        doc: clean_up_score_string(solr_output_explaination[doc].split("=")[0])
        for doc in solr_output["debug"]["explain"]
    }

    return doc_score_list


if __name__ == "__main__":
    # input:
    solr_url = "http://localhost:8983/solr/#/core-x/"

    list_queries = []
    # Generating the list of queries
    for input_query in [
        "majority of the votes",
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
    ]:
        for type_query in ["ocronly", "all"]:
            for op_type in ["AND", "OR", None]:
                list_queries.append(
                    {
                        "query_fields": type_query,
                        "query_string": input_query,
                        "operator": op_type,
                    }
                )

    for query in list_queries:
        fl = ["author", "id", "title"]
        print(f"Solr query {query['query_string']} with operator {query['operator']}")

        # Create query object
        Q = HTFullTextQuery(config_query=query['query_fields'])

        ht_search = HTFullTextSearcher(engine_uri=solr_url, ht_search_query=Q)

        solr_output = ht_search.solr_result_query_dict(
            url=solr_url,
            query_string=query["query_string"],
            fl=fl,
            operator=query["operator"]
        )

        if solr_output["response"]["numFound"] == 0:
            print(f'No results found for query {query["query_string"]}')
            continue
        df = pd.DataFrame(solr_output["response"]["docs"])

        doc_score_dict = create_doc_score_dataframe(solr_output["debug"]["explain"])

        df["score"] = df["id"].map(doc_score_dict)

        df.to_csv(
            path_or_buf=f'{query["query_fields"]}_{query["query_string"]}_{query["operator"]}_solr6.csv',
            index=False,
            sep="\t",
        )
