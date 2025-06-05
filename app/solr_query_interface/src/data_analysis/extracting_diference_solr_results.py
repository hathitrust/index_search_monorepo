
import os
import pathlib
from argparse import ArgumentParser

import matplotlib.pyplot as plt
import pandas as pd
from generate_query_results_in_batch import get_list_phrases
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

"""
What are the questions we want to answer?

1. How many queries are we comparing? DONE
2. How many queries results are identical? DONE
6. How many queries results have the same ids in both engines? DONE

4. How many queries results have the same ids in the top n=5,10?
5. How many queries results have the same ids in the top n=5,10,15?
7. How many queries results have different ids in both engines?
8. How many queries results have the same ids in both engines and the order is different?
9. How many queries results have different ids in both engines and the order is different?
10. How many queries results have different ids in both engines and the order is the same?
11. How many queries results have the same ids in both engines and the order is the same?
12. How many queries results have the same ids in both engines and the order is the same and the scores are the same?
13. How many queries results have the same ids in both engines and the order is the same and the scores are different?
14. How many queries results have the same ids in both engines and the order is the same and the scores are different in
 the top n=5,10,15?
 
"""


def get_different_ids(list_a, list_b):
    diff_elements = []
    for i in sorted(list_a):
        if i not in list_b:
            diff_elements.append(i)
    for i in sorted(list_b):
        if i not in list_a:
            diff_elements.append(i)
    return list(set(diff_elements))


def get_different_sorted_ids(list_a, list_b):
    diff_elements = []
    for i, item in enumerate(list_a):
        try:
            if item != list_b[i]:
                diff_elements.append(i)
        except IndexError as e_index:
            diff_elements.append(i)
            logger.error(f"Index Error {e_index}")

    for i, item in enumerate(list_b):
        try:
            if item != list_a[i]:
                diff_elements.append(i)
        except IndexError as e_index:
            diff_elements.append(i)
            logger.error(f"Index Error {e_index}")

    return list(set(diff_elements))


def percentage(part, whole):
    return 100 * float(part) / float(whole)


if __name__ == "__main__":

    parser = ArgumentParser()

    parser.add_argument("--list_phrase_file", help="TXT file containing the list of phrase to search",
                        default='')

    args = parser.parse_args()

    list_queries = []

    list_phrases = get_list_phrases(args.list_phrase_file)

    logger.info(f"Total string queries {len(list_phrases)}.")
    kind_query = ["AND", "OR", None]
    logger.info(f"Total kind of queries: {len(kind_query)}")

    # Expected number of queries to compare: total of kind_query * string_queries (3 * 17) = 51 to compare
    logger.info(f"Expected comparison {len(list_phrases) * len(kind_query)}")
    # Generating the list of queries
    for input_query in list_phrases:
        for type_query in ["ocronly"]:
            for op_type in kind_query:
                list_queries.append(
                    {
                        "query_fields": type_query,
                        "query_string": input_query,
                        "operator": op_type,
                    }
                )

    result_slides = [5, 10, 30]

    query_stats = {
        "ident_results": 0,
        "ident_id_top_5": 0,
        "ident_id_range5-20": 0,
        "diff_id_top_5": 0,
        "diff_id_range5-20": 0,
        "diff_id_top_20_to_end": 0,
        "same_ids_both_engines": 0,
    }
    count_diff = []
    total_comparison = 0
    hits_dict = {}
    for query in list_queries:
        df_A = None
        df_B = None
        logger.info("***************")
        logger.info(query)

        a_path = f'scripts/query_results/{query["query_fields"]}_{query["query_string"]}_{query["operator"]}_prod.csv'
        logger.info("/".join([os.getcwd(), a_path]))
        if pathlib.Path("/".join([os.getcwd(), a_path])).is_file():
            df_A = pd.read_csv("/".join([os.getcwd(), a_path]), sep="\t")
        else:
            logger.info(f"File {a_path} does not exist")
            continue
        b_path = f'scripts/query_results/{query["query_fields"]}_{query["query_string"]}_{query["operator"]}_dev.csv'
        logger.info("/".join([os.getcwd(), b_path]))
        if pathlib.Path("/".join([os.getcwd(), b_path])).is_file():
            df_B = pd.read_csv("/".join([os.getcwd(), b_path]), sep="\t")
        else:
            logger.info(f"File {b_path} does not exist")
            continue

        # total of difference
        diff = get_different_sorted_ids(df_A["id"].to_list(), df_B["id"].to_list())

        count_diff.append(len(diff))
        total_comparison = total_comparison + 1
        try:
            if df_A[["id", "author", "title"]].equals(df_B[["id", "author", "title"]]):
                logger.info(
                    "Identical results")  # I did not expect this case, because at least the scores should be different
                query_stats["ident_results"] += 1

            if list(df_A["id"][0:5]) == list(df_B["id"][0:5]):
                logger.info("Identical ids in top 5")
                query_stats["ident_id_top_5"] += 1
            else:
                logger.info("Different ids in top 5")
                query_stats["diff_id_top_5"] += 1
            if list(df_A["id"][5:20]) == list(df_B["id"][5:20]):
                logger.info("Identical ids in the range 5 to 20")
                query_stats["ident_id_range5-20"] += 1
            else:
                logger.info("Different ids in the range 5 to 20")
                query_stats["diff_id_range5-20"] += 1

            if list(df_A["id"][20:]) != list(df_B["id"][20:]):
                logger.info("Different ids from top 20 to end")
                query_stats["diff_id_top_20_to_end"] += 1

            if len(get_different_ids(df_A["id"].to_list(), df_B["id"].to_list())) == 0:

                logger.info("The same ids in both engines")
                query_stats["same_ids_both_engines"] += 1
            else:
                logger.info("Different ids in both engines")
                logger.info(query)

            if len(set(df_A["id"].sort_values()) ^ set(df_B["id"].sort_values())) > 0:
                logger.info(f"List of different ids {set(df_A['id']) ^ set(df_B['id'])}")
        except AttributeError as e_attribute:
            logger.error(f"Some of the dataframe does not exist Error {e_attribute}")
        except NameError as e_name:
            logger.error(f"Some of the dataframe does not exist Error {e_name}")
        except TypeError as e_type:
            logger.error(f"Some of the dataframe does not exist Error {e_type}")

    logger.info(f"Total comparison {total_comparison}")
    logger.info(query_stats)
    query_stats_percentage = {key: percentage(value, total_comparison) for key, value in query_stats.items()}
    logger.info(query_stats_percentage)

    plt.figure(figsize=(10, 7))

    names = list(query_stats.keys())
    values = list(query_stats.values())

    logger.info(names)
    logger.info(count_diff)

    plt.bar(names, values)
    plt.title("Query stats")
    plt.ylabel("Total of queries")
    plt.xlabel("Categories")

    plt.show()
