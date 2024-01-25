# Perl file: LS::Query:FullTest.pm

# import Utils
# from Search import Query
# from Access import Rights

import os

from ht_query.ht_query import HTSearchQuery
from typing import Text
from config_search import QUERY_PARAMETER_CONFIG_FILE, FACET_FILTERS_CONFIG_FILE


class HTFullTextQuery(HTSearchQuery):

    """
    Make full-text search queries from user request

    Query parser, query attributes and returns
    """

    def __init__(
        self,
        config_query: Text = "all",
        config_query_path: Text = QUERY_PARAMETER_CONFIG_FILE,
        user_id: Text = None,
        config_facet_field: Text = None,
        config_facet_field_path: Text = FACET_FILTERS_CONFIG_FILE,
    ):
        """
        Constructor to create the Solr query
        :param config_query: Name of the query defined in the config_query.yaml file
        :param config_query_path: Path to the config_query.yaml file
        :param user_id: Use to set up the filters
        :param config_facet_field: Name of the entry with facets and filters in config_facet_field.yaml file.
        If None, then not facet or filter will be used in the query
        :param config_facet_field_path: Path to the config_facet_field.yaml file
        """

        self.cached_solr_query_string = False  # TODO Use Case: Keep the query on cache for avoiding repeat MySql queries

        super().__init__(
            config_query=config_query,
            config_query_path=config_query_path,
            user_id=user_id,
            config_facet_field=config_facet_field,
            config_facet_field_path=config_facet_field_path,
        )

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
    Q = HTFullTextQuery(
        config_query="all",
        config_query_path=QUERY_PARAMETER_CONFIG_FILE,
        config_facet_field=None,
        config_facet_field_path=FACET_FILTERS_CONFIG_FILE,
    )

    solr_query = Q.make_solr_query(query_string=query_string, operator="OR")

    print(solr_query)
