# Perl file: LS::Query:FullTest.pm
from typing import Text

from ht_full_text_search.config_search import QUERY_PARAMETER_CONFIG_FILE, FACET_FILTERS_CONFIG_FILE
from ht_query.ht_query import HTSearchQuery


class HTFullTextQuery(HTSearchQuery):
    """
    Make full-text search queries from user request
    Query parser, query attributes and returns
    """

    # TODO: In the future, we should review this classs. It is not clear if we need it or not.
    # TODO: We will need it, in case you will implement a new search engine in addition to the full text search engine

    def __init__(
            self,
            config_query: Text = "all",
            config_query_path: Text = QUERY_PARAMETER_CONFIG_FILE,
            user_id: Text = None,
            config_facet_field: Text = None,
            config_facet_field_path: Text = FACET_FILTERS_CONFIG_FILE
    ):
        """
        Constructor to create the Solr query
        :param config_query: Name of the query defined in the config_query.yaml file
        :param config_query_path: Path to the config_query.yaml file
        :param user_id: Use to set up the filter
        :param config_facet_field: Name of the entry with facets and filters in config_facet_field.yaml file.
        If None, then not facet or filter will be used in the query
        :param config_facet_field_path: Path to the config_facet_field.yaml file
        """

        # TODO Use Case: Keep the query on cache for avoiding repeat MySql queries
        self.cached_solr_query_string = False

        super().__init__(
            config_query=config_query,
            config_query_path=config_query_path,
            user_id=user_id,
            config_facet_field=config_facet_field,
            config_facet_field_path=config_facet_field_path,
        )


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

    solr_query = Q.make_solr_query(q_string=query_string, operator="OR")

    print(solr_query)
