from ht_searcher.ht_searcher import HTSearcher
import pandas as pd

def clean_up_score_string(score_string):

    return score_string.strip('\n').strip('')

def create_doc_score_dataframe(solr_output_explaination):

    doc_score_list = {doc: clean_up_score_string(solr_output_explaination[doc].split('=')[0]) for doc in solr_output['debug']['explain']}

    return doc_score_list

if __name__ == "__main__":
    # input:
    solr_url = "http://localhost:8983/solr/#/core-x/"

    for query_string in ["Natural history", "26th Regiment of Foot"]:
        fl = ["author", "id", "title"]
        #query_string = 'q=_query_:"{!dismax qf=ocr}health"&fl=author,id,title'

        ht_search = HTSearcher(solr_url)
        solr_output = ht_search.solr_result(url=solr_url, query_string=query_string, fl=fl)

        df = pd.DataFrame(solr_output['response']['docs'])

        doc_score_dict = create_doc_score_dataframe(solr_output['debug']['explain'])

        df['score'] = df['id'].map(doc_score_dict)

        df.to_csv(path_or_buf=f'{query_string}_solr6_ClassicSimilarity.csv', index=False, sep='\t')
