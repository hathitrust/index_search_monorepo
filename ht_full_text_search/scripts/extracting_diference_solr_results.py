import pandas as pd
import os

if __name__ == "__main__":

    for query in ["Natural history", "26th Regiment of Foot"]:
        df_A = pd.read_csv('/'.join([os.getcwd(), f'{query}_solr6_ClassicSimilarity.csv']), sep='\t')
        df_B = pd.read_csv('/'.join([os.getcwd(), f'{query}_solr8_MB25Similarity.csv']), sep='\t')

        print(query)
        if df_A.equals(df_B):
            print('Identical results') # I did not expect this case, because at least the scores should be different
        if list(df_A['id']) == list(df_B['id']): #Both engine retrieve the same list of ids
            print('Identical ids and order')
        if list(df_A['id'][0:5]) == list(df_B['id'][0:5]):
            print('Identical ids in top 5')
        if list(df_A['id'][5:15]) != list(df_B['id'][5:15]):
            print('Different ids in top 5 to 15')
        if len(set(df_A['id']).intersection(set(df_B['id']))) == 15:
            print('The same ids in both engines')
        if len(set(df_A['id']) ^ set(df_B['id'])) > 0:
            print(f"List of different ids {set(df_A['id']) ^ set(df_B['id'])}")

