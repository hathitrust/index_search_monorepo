from ht_searcher.ht_searcher import HTSearcher
from ht_full_text_search.ht_full_text_query import HTFullTextQuery
from config_search import SOLR_URL, FULL_TEXT_SEARCH_SHARDS
from typing import Text

from argparse import ArgumentParser
import os



"""
LS::Operation::Search ==> it contains all the logic about interleaved adn A/B tests
"""

class HTFullTextSearcher(HTSearcher):

    def __init__(self, engine_uri: Text = None,
                 timeout: int = None,
                 ht_search_query: HTFullTextQuery = None,
                 use_shards: bool= False):

        super().__init__(engine_uri=engine_uri, timeout=timeout,
                         ht_search_query=ht_search_query,
                         use_shards=use_shards)
        # TODO implement the of AB test and interleave
        """
        self.AB_config = C.get_object('AB_test_config')
        self.use_interleave = self.AB_config['_']['use_interleave']
        self.use_B_query = self.AB_config['_']['use_B_query']
        self.N_Interleaved = self.AB_config['_']['Num_Interleaved_Results']
        """
    """
    def do_query(self, C, searcher, user_query_string, query_type, start_row, num_rows, AB):

        #Note that this code assumes that you have the necessary Python modules/packages installed
        #(LS.Query.Facets, LS.Result.JSON.Facets, etc.). You may need to install them if you haven't done so already.
        #Let me know if you need any further assistance!
        

        Q = LS.Query.Facets(C, user_query_string, None, {
            'solr_start_row': start_row,
            'solr_num_rows': num_rows,
            'query_type': query_type
        })

        rs = LS.Result.JSON.Facets(query_type)
        rs = searcher.get_populated_Solr_query_result(C, Q, rs, AB)

        # Log
        Q.log_query(C, searcher, rs, 'ls', AB)
        return rs, Q

    def execute_operation(self, C):
        self.act.execute_operation(C)

        self.C = C
        print('execute operation="Search"')

        cgi = self.C.get_object('CGI')
        act = self.get_action()

        test_collection(self.C, act)

        user_solr_start_row, user_solr_num_rows, current_sz = self.get_solr_page_values(self.C)
        cgi, primary_type, secondary_type = get_types(cgi)
        result_data = {}

        if not self.use_interleave:
            to_search = {
                'a': 1
            }
            if self.use_B_query:
                to_search['b'] = 1
            result_data = self.do_queries(self.C, to_search, primary_type, user_solr_start_row, user_solr_num_rows)
        else:
            if user_solr_start_row == 0 or user_solr_start_row < self.N_Interleaved:
                if user_solr_start_row + user_solr_num_rows > self.N_Interleaved:
                    result_data = self.get_mixed_results(self.C, primary_type, user_solr_start_row, user_solr_num_rows,
                                                         self.N_Interleaved)
                else:
                    i_start = user_solr_start_row
                    i_rows = user_solr_num_rows
                    result_data = self.__do_interleave(self.C, primary_type, i_start, i_rows)
            else:
                counter_a = self.get_counter_a(self.C, self.N_Interleaved, primary_type)
                result_data = self.__do_A_search_from_counter(self.C, self.N_Interleaved, primary_type,
                                                              user_solr_start_row, user_solr_num_rows, counter_a)

        primary_Q = result_data['primary_Q']

        search_result_data = {
            'primary_result_object': result_data['primary_rs'],
            'secondary_result_object': result_data['secondary_rs'],
            'B_result_object': result_data['B_rs'],
            'interleaved_result_object': result_data['i_rs'],
            'il_debug_data': result_data['il_debug_data'],
            'well_formed': {
                'primary': primary_Q.well_formed(),
                'processed_query_string': primary_Q.get_processed_query_string(),
                'unbalanced_quotes': primary_Q.get_unbalanced_quotes(),
            },
            'user_query_string': result_data['user_query_string'],
        }

        act.set_transient_facade_member_data(self.C, 'search_result_data', search_result_data)

        return ST_OK

    def get_il_debug_data(rd):
        debug_count = {}
        A_id_ref = None
        B_id_ref = None
        I_id_ref = None

        if 'primary_rs' in rd:
            A_id_ref = rd['primary_rs']['result_ids']
        if 'B_rs' in rd:
            B_id_ref = rd['B_rs']['result_ids']
        if 'B_rs' in rd:
            I_id_ref = rd['i_rs']['result_ids']

        if A_id_ref is not None:
            debug_count['a'] = len(A_id_ref)
        if B_id_ref is not None:
            debug_count['b'] = len(B_id_ref)
        if I_id_ref is not None:
            debug_count['i'] = len(I_id_ref)

        return debug_count

    def get_mixed_results(self, C, primary_type, user_solr_start_row, user_solr_num_rows, N_Interleaved):
        result_data = {}
        end_row = user_solr_start_row + user_solr_num_rows
        A_rows_needed = end_row - N_Interleaved
        I_rows_needed = user_solr_num_rows - A_rows_needed
        i_start = N_Interleaved - I_rows_needed

        i_result_data = self.__do_interleave(C, primary_type, i_start, I_rows_needed)

        debug_output = len(i_result_data['i_rs']['result_response_docs_arr_ref'])

        counter_a = self.get_counter_a(C, N_Interleaved, primary_type)

        solr_start_row = N_Interleaved
        solr_num_rows = A_rows_needed

        a_result_data = self.__do_A_search_from_counter(C, N_Interleaved, primary_type, solr_start_row,
                                                        solr_num_rows, counter_a)

        i_array = i_result_data['i_rs']['result_response_docs_arr_ref']
        a_array = a_result_data['a_rs']['result_response_docs_arr_ref']
        result_ids = i_result_data['i_rs']['result_ids'] + a_result_data['a_rs']['result_ids']

        i_result_data['i_rs']['result_response_docs_arr_ref'] = i_array + a_array
        i_result_data['i_rs']['result_ids'] = result_ids

        return i_result_data

    def __do_interleave(self, C, primary_type, i_start, i_rows):
        i_result_data = {}

        i_result_data['i_rs'] = {
            'result_response_docs_arr_ref': [],
            'result_ids': [],
        }

        ####################
        ### DO INTERLEAVE ###
        ####################

        interleaver = LS::Interleaver::Balanced(interleave_count=i_start + i_rows)
        interleaver.set_start(i_start)
        interleaver.set_num_results(i_rows)
        interleaver.set_type(primary_type)
        interleaver.set_solr_params({})

        it_search_results = interleaver.get_interleaved_search_results()
        i_rs = it_search_results[0]

        result_response_docs_arr_ref = i_result_data['i_rs']['result_response_docs_arr_ref']
        result_ids = i_result_data['i_rs']['result_ids']

        for rs in it_search_results:
            result_response_docs_arr_ref.extend(rs['result_response_docs_arr_ref'])
            result_ids.extend(rs['result_ids'])

        ####################
        ### END INTERLEAVE #
        ####################

        i_result_data['i_rs']['result_response_docs_arr_ref'] = result_response_docs_arr_ref
        i_result_data['i_rs']['result_ids'] = result_ids

        return i_result_data

    def __do_A_search_from_counter(self, C, N_Interleaved, primary_type, user_solr_start_row, user_solr_num_rows, counter_a):
        a_result_data = {}

        a_result_data['a_rs'] = {
            'result_response_docs_arr_ref': [],
            'result_ids': [],
        }

        #######################
        ### DO A SEARCH FROM ###
        #######################

        solr_start_row = N_Interleaved + user_solr_start_row
        solr_num_rows = user_solr_num_rows

        a_searcher = LS::Searcher::Facets({'C': C})

        a_searcher.set_type(primary_type)
        a_searcher.set_start_row(solr_start_row)
        a_searcher.set_num_rows(solr_num_rows)
        a_searcher.set_sort_field_name('UnnamedSortField')

        a_searcher.adjust_num_threads()

        query = a_searcher.get_query(primary_type, {'solr_start_row': solr_start_row,
                                                    'solr_num_rows': solr_num_rows})

        a_rs = a_searcher.get_search_results({'primary_Q': query, 'B_result_object': None})

        # does result ids exist or just result_id?
        if 'result_ids' in a_rs:
            result_ids = a_result_data['a_rs']['result_ids']
            result_ids.extend(a_rs['result_ids'])
        else:
            result_id = a_result_data['result_id']
            result_id.extend(a_rs['result_id'])

        #######################
        ### END A SEARCH FROM #
        #######################

        a_result_data['a_rs']['result_response_docs_arr_ref'] = result_response_docs_arr_ref
        a_result_data['a_rs']['result_ids'] = result_ids

        return a_result_data
    """

if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))
    parser.add_argument("--query_string", help="Query string", default=None)
    parser.add_argument("--fl", help="Fields to return", default=["author", "id", "title"])
    parser.add_argument("--solr_url", help="Solr url", default=None)
    parser.add_argument("--operator", help="Operator", default="AND")
    parser.add_argument("--query_config", help="Type of query acronly or all", default="all")
    parser.add_argument("--use_shards", help="If the query should include shards", default=False)


    # input:
    args = parser.parse_args()

    # Receive as a parameter an specific solr url
    if args.solr_url:
        solr_url = args.solr_url
    else: # Use the default solr url, depending on the environment. If prod environment, use shards
        solr_url = SOLR_URL[args.env]

    query_string = "chief justice"
    fl = ["author", "id", "title"]
    use_shards = False

    if args.env == "prod":
        use_shards = FULL_TEXT_SEARCH_SHARDS
    else:
        use_shards = args.use_shards # By default is False

    # Create query object
    Q = HTFullTextQuery(config_query="all")

    # Create full text searcher object
    ht_full_search = HTFullTextSearcher(engine_uri=solr_url,
                                        ht_search_query=Q,
                                        use_shards=use_shards)
    solr_output = ht_full_search.solr_result(
        url=solr_url, query_string=query_string, fl=fl, operator="AND"
    )

    print(solr_output)