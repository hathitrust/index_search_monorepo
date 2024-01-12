# Perl file: LS::Query:FullTest.pm

# import Utils
# from Search import Query
# from Access import Rights

import os
import sys
import inspect

from ht_query.ht_query import HTSearchQuery


currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)




class HTFullTextQuery(HTSearchQuery):

    """
    Make full-text search queries from user request

    Query parser, query attributes and returns
    """

    def __init__(self, query_string, internal):
        self.cached_solr_query_string = False  # TODO Use Case: Keep the query on cache for avoiding repeat MySql queries
        self.query_configuration = { # TODO Retrieve this parameters from a Config file
            "solr_num_rows": 100,
            "solr_start_row": 0,
            "full_text_query": True
        }
        super().__init__(query_string=query_string, internal=internal)

    # def AFTER_Query_initialize(self, C, internal, config_hashref):
    #    self.query_configuration = config_hashref

    def get_id_arr_ref(self):
        return self.id_arr_ref

    def full_text_query(self, C):
        query_config = self.query_configuration
        return query_config["full_text_query"]

    def rows_requested(self, C):
        query_config = self.query_configuration
        return query_config["solr_num_rows"] > 0

    def get_start_row(self, C):
        query_config = self.query_configuration
        return query_config["solr_start_row"]

    def get_solr_num_rows(self, C):
        query_config = self.query_configuration
        return query_config["solr_num_rows"]

    def cache_solr_query_string(self, s):
        self.cached_solr_query_string = s

    def get_cached_solr_query_string(self):
        return self.cached_solr_query_string

    def get_solr_query_string(self, C):
        if self.get_cached_solr_query_string():
            return self.get_cached_solr_query_string()

        user_query_string = (
            self.query_string
        )  # TODO Process query string: self.get_processed_user_query_string()
        USER_Q = f"q={user_query_string}"
        FL = "&fl=title,author,date,rights,id,record_no,score"
        VERSION = f"&version={self.get_Solr_XmlResponseWriter_version()}"
        INDENT = "&indent=on" if "TERM" in os.environ else "&indent=off"

        solr_start, solr_rows = 0, 0
        if self.rows_requested(C):
            solr_start = self.get_start_row(C)
            solr_rows = self.get_solr_num_rows(C)
        START_ROWS = f"&start={solr_start}&rows={solr_rows}"

        FQ = ""
        if self.full_text_query(C):
            attr_list_aryref = [1, 7]
            try:
                attr_list_aryref = (
                    []
                )  # TODO Get list attributes by Rights Rights.get_fulltext_attr_list(C)
            except Exception:
                pass
            FQ = "&fq=rights:(" + " OR ".join(map(str, attr_list_aryref)) + ")"

        solr_query_string = USER_Q + FL + FQ + VERSION + START_ROWS + INDENT

        # self.cache_solr_query_string(solr_query_string)

        return solr_query_string

    def get_solr_internal_query_string(self):
        query_string = self.get_query_string().lower()
        INTERN_Q = f"q={query_string}"
        FL = "&fl=*,score"
        VERSION = f"&version={self.get_solr_XmlResponseWriter_version()}"
        START_ROWS = "&start=0&rows=1000000"
        INDENT = "&indent=off"

        solr_query_string = INTERN_Q + FL + VERSION + START_ROWS + INDENT

        return solr_query_string

    def get_query_string(self):
        pass


if __name__ == "__main__":
    # Example usage
    query_string = "example query"
    internal = [[1, 234, 4, 456, 563456, 43563, 3456345634]]
    Q = HTFullTextQuery(query_string, internal)
    solr_query_string = Q.get_solr_query_string("C")
    print(solr_query_string)
