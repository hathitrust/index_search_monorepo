import pandas as pd
import os
import pathlib
import matplotlib.pyplot as plt

if __name__ == "__main__":

    list_queries = []
    # Generating the list of queries
    for input_query in ["majority of the votes", "chief justice", "Natural history",
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
                        "Genealogy"]:
        for type_query in ["ocronly", "all"]:
            for op_type in ["AND", "OR", None]:
                list_queries.append({
                    "query_fields": type_query,
                    "query_string": input_query,
                    "operator": op_type
                })

    query_stats = {
        'ident_results': 0,
        'ident_ids_order': 0,
        'ident_id_top_5': 0,
        'diff_id_top_5': 0,
        'diff_id_top_5_to_15': 0,
        'same_ids_both_engines': 0
    }
    total_comparison = 0
    for query in list_queries:
        df_A = None
        df_B = None
        print('***************')
        print(query)

        # f'{query["query_fields"]}_{query["query_string"]}_{query["operator"]}_solr8_BM25_similarity.csv'
        a_path = f'{query["query_fields"]}_{query["query_string"]}_{query["operator"]}_solr6.csv'
        if pathlib.Path(a_path).is_file():
            df_A = pd.read_csv('/'.join([os.getcwd(), a_path]), sep='\t')
        else:
            print(f'File {a_path} does not exist')
            continue
        b_path = f'{query["query_fields"]}_{query["query_string"]}_{query["operator"]}_solr8.csv'
        if pathlib.Path(b_path).is_file():
            df_B = pd.read_csv('/'.join([os.getcwd(), b_path]), sep='\t')
        else:
            print(f'File {b_path} does not exist')
            continue
        total_comparison = total_comparison + 1
        try:
            if df_A[['id', 'author', 'title']].equals(df_B[['id', 'author', 'title']]):
                print('Identical results') # I did not expect this case, because at least the scores should be different
                query_stats['ident_results'] += 1
            if list(df_A['id']) == list(df_B['id']): #Both engine retrieve the same list of ids
                print('Identical ids and order')
                query_stats['ident_ids_order'] += 1
            if list(df_A['id'][0:5]) == list(df_B['id'][0:5]):
                print('Identical ids in top 5')
                query_stats['ident_id_top_5'] += 1
            else:
                print('Different ids in top 5')
                query_stats['diff_id_top_5'] += 1
            if list(df_A['id'][5:15]) != list(df_B['id'][5:15]):
                print('Different ids in top 5 to 15')
                query_stats['diff_id_top_5_to_15'] += 1
            #if len(set(df_A['id']).intersection(set(df_B['id']))) == len(set(df_A['id'])) + len(set(df_B['id'])):
            if set(df_A['id']).intersection(df_B['id']) == set(df_B['id']) and set(df_A['id']).intersection(df_B['id']) == set(df_A['id']):
                print('The same ids in both engines')
                query_stats['same_ids_both_engines'] += 1
            if len(set(df_A['id']) ^ set(df_B['id'])) > 0:
                print(f"List of different ids {set(df_A['id']) ^ set(df_B['id'])}")
        except AttributeError as e_attribute:
            print(f'Some of the dataframe does not exist Error {e_attribute}')
        except NameError as e_name:
            print(f'Some of the dataframe does not exist Error {e_name}')
        except TypeError as e_type:
            print(f'Some of the dataframe does not exist Error {e_type}')

    print(query_stats)
    print(total_comparison)

    fig = plt.figure(figsize=(10, 7))

    names = list(query_stats.keys())
    values = list(query_stats.values())

    ax = fig.add_subplot()
    ax.set_title('Query stats')
    ax.set_ylabel('Total of queries')
    ax.set_xlabel('Categories')
    ax.bar(range(len(query_stats)), values, tick_label=names)
    ax.set_xticklabels(names, rotation=10, ha='right')
    #plt.bar(range(len(query_stats)), values, tick_label=names)
    plt.show()
