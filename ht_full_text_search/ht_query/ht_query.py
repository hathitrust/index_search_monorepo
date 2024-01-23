
import re
import yaml
from typing import Text, List, Dict
from functools import reduce

from ht_utils.ht_access_rights import (
    get_fulltext_attr_list,
    g_access_requires_holdings_attribute_values,
    get_access_type_determination,
    SSD_USER,
    g_access_requires_brittle_holdings_attribute_value,
)


class HTSearchQuery:
    def __init__(
        self,
        config_query: Text = "all",
        config_query_path: Text = None,
        user_id: Text = None,
        config_facet_field: Text = None,
        config_facet_field_path: Text = None
    ):
        """
        Constructor to create the Solr query
        :param config_query: Name of the query defined in the config_query.yaml file
        :param config_query_path: Path to the config_query.yaml file
        :param user_id: Use to set up the filters
        :param config_facet_field: Name of the entry with facets and filters in config_facet_field.yaml file.
        If None, then not facet or filter will be used in the query
        :param config_facet_field_path: Path to the config_facet_field.yaml file
        :param internal: # TODO Parameter extracted from the perl code. I should check if it is necessary
        """

        # TODO: Define default values to initialize the query
        # self.query_string = query_string
        self.config_query = config_query

        try:
            self.solr_parameters = HTSearchQuery.initialize_solr_query(
                config_query_path, self.config_query
            )
        except Exception as e:
            print(f"File {config_query_path} does not exist")
            self.solr_parameters = {} # Empty dictionary
        try:
            self.solr_facet_filters = HTSearchQuery.initialize_solr_query(
                config_facet_field_path, config_facet_field
            )
        except Exception as e:
            print(f"File {config_facet_field} does not exist")
            self.solr_facet_filters = {}  # Empty dictionary
            pass

        self.user_id = user_id  # parameter used to set up the filters


    # TODO: perl method that probably we will remove
    @staticmethod
    def initialize_solr_query(config_file, conf_query: Text = "all"):
        with open(config_file, "r") as file:
            data = yaml.safe_load(file)

        return data[conf_query]

    # Function to convert a string in a dictionary
    @staticmethod
    def query_string_to_dict(string_query):
        return dict(
            qc.split("=") if qc[0] != "q" else [qc[0], "=".join(qc.split("=")[1:])]
            for qc in string_query.split("&")
        )

    @staticmethod
    def create_boost_query_fields(query_fields: List[List]) -> List:
        """
        This function create the solr qf (query fields).
        Each field is assigned a boost factor to increase or decrease their importance in the query
        Transform a list of fields and their boost factor in Solr format"""

        return ["^".join(map(str, field)) for field in query_fields]

    def create_boost_phrase_fields(self):
        pf = [
            # phrase fields ==> Once the list of matching documents has been identified using the fq and qf parameters, the pf parameter can be used to "boost" the score of documents in cases where all of the terms in the q parameter appear in close proximity.
            "title_ab^10000",
            "titleProper^1500",
            "title_topProper^1000",
            "title_restProper^800",
            "series^100",
            "series2^100",
            "author^1600",
            "author2^800",
            "topicProper^200",
            "allfieldsProper^100",
        ]
        return pf

    def facet_creator(self, facet_dictionary: Dict = None) -> Dict:
        return reduce(lambda key, value: {**key, **value}, facet_dictionary)

    def query_filter_creator(self, filter_name, filter_value):
        filter_string = (
            " OR ".join(map(str, filter_value))
            if isinstance(filter_value, list)
            else filter_value
        )

        query_filters = f"{filter_name}:({filter_string})"
        return query_filters

    @staticmethod
    def get_exact_phrase_query(query_string: Text) -> Text:
        return '"'.join(("", query_string, ""))

    @staticmethod
    def manage_string_query(input_phrase: Text, operator: Text = None) -> Dict:
        """
        This function transform a query_string in Solr string format

        e.g. information OR issue # boolean opperator (any of these words)
        e.g. '"information issue"' # exact phrase query
        e.g. "information issue" # all these words
        :param input_phrase:
        :param operator: It could be, all, exact_match or boolean_opperator
        :return:
        """

        query_string_dict = {"q": HTSearchQuery.get_exact_phrase_query(input_phrase)}

        if operator == "OR":
            query_string_dict = {"q": input_phrase, "q.op": operator}
        elif operator == "AND":
            query_string_dict = {"q": input_phrase, "q.op": operator}
        return query_string_dict

    def make_solr_query(
        self,
        query_string: Text = None,
        operator: Text = None,  # It could be, None (exact_match), "AND" (all these words) or "OR" (any of these words)
        start: int = 0,
        rows: int = 15,
        fl: List = None,
        pf: bool = True,  # It is False for Only Text query
        filter: bool = False,  # If the query is using filter, then use config_facet_filters.yaml to create the fq parameter
    ):
        query_dict = {
            "defType": self.solr_parameters.get("parser")
            if self.solr_parameters.get("parser")
            else "editmas",  # query parser
            "start": start,
            "rows": rows,
            "fl": self.solr_parameters.get("fl")
            if self.solr_parameters.get("fl")
            else [],
            "indent": "on",
            "debug": self.solr_parameters.get("debug"),
            "mm": self.solr_parameters.get("mm"),  # 100 % 25,  # mm = minimum match
            "tie": self.solr_parameters.get("tie"),  # "0.9",  # tie = tie breaker
            "qf": HTSearchQuery.create_boost_query_fields(
                self.solr_parameters.get("qf")
            ),  # qf = query fields. Each field is assigned a boost factor to increase or decrease their importance in the query
            "pf": HTSearchQuery.create_boost_phrase_fields(
                self.solr_parameters.get("pf")
            )
            if self.solr_parameters.get("pf")
            else [],
        }

        if not query_string:
            query_dict.update({"q": "*:*"})
        else:
            query_dict.update(HTSearchQuery.manage_string_query(query_string, operator))

        if self.solr_facet_filters:
            query_dict.update(self.facet_creator(self.solr_facet_filters.get("facet")))

        if fl:
            query_dict.update({"fl": fl})

        # Add the filter query
        if filter:
            query_dict.update(
                {
                    "fq": self.query_filter_creator(
                        "rights",
                        [
                            25,
                            15,
                            18,
                            1,
                            21,
                            23,
                            19,
                            13,
                            11,
                            20,
                            7,
                            10,
                            24,
                            14,
                            17,
                            22,
                            12,
                        ],
                    )
                }
            )
        return query_dict

    def AFTER_Query_initialize(self):
        pass
        # raise NotImplementedError("AFTER_Query_initialize() in SearchQuery is pure virtual")

    def get_Solr_XmlResponseWriter_version(self):
        return "2.2"

    def get_Solr_query_string(self):
        pass
        # raise NotImplementedError("get_Solr_query_string() in SearchQuery is pure virtual")

    def get_processed_user_query_string(self, query_string):
        user_query_string = query_string if query_string else self.get_query_string()
        user_query_string = self.filter_lucene_chars(user_query_string)

        tokens = self.parse_preprocess(user_query_string)

        valid = True
        if any(token in ["AND", "OR", "(", ")"] for token in tokens):
            valid = HTSearchQuery.valid_boolean_expression(tokens)
            if valid:
                self.set_was_valid_boolean_expression()

        if not valid:
            self.set_well_formed(False)

            final_tokens = [
                HTSearchQuery.get_final_token(t)
                for t in tokens
                if HTSearchQuery.get_final_token(t)
            ]
            user_query_string = " ".join(final_tokens)
        else:
            self.set_well_formed(True)

        self.set_processed_query_string(user_query_string)
        # DEBUG('parse', lambda: f"Final processed user query: {user_query_string}")

        return user_query_string

    def parse_preprocess(self):
        pass

    @staticmethod
    def get_final_token(s):
        if re.search(r"([\(\)]|^AND$|^OR$)", s):
            return ""
        return s

    def set_processed_query_string(self, s):
        self.processed_query_string = s

    def get_Solr_no_fulltext_filter_query(self, C):
        """Construct a filter query informed by the authentication and holdings
        environment for 'search-only'.  This is the negation of
        get_Solr_fulltext_filter_query()"""

        fulltext_FQ_arg = self._HELPER_get_Solr_fulltext_filter_query_arg(C)
        full_no_fulltext_FQ_string = "fq=(NOT+" + fulltext_FQ_arg + ")"
        return full_no_fulltext_FQ_string

    def get_Solr_fulltext_filter_query(self, C):
        full_fulltext_FQ_string = (
            "fq=" + self._HELPER_get_Solr_fulltext_filter_query_arg(C)
        )
        return full_fulltext_FQ_string

    def _HELPER_get_Solr_fulltext_filter_query_arg(self, C):
        """ "
        TO implement this function I should see the code in:
         * mdp-lib/Access/Rights.pm
         * mdp-lib/RightsGlobals.pm
         This function will be used to create the Solr filter query
        """
        # fulltext_attr_list_ref = Access.Rights.get_fulltext_attr_list(C)

        fulltext_attr_list_ref = get_fulltext_attr_list(C)
        holdings_qualified_attr_list = []
        unqualified_attr_list = list(fulltext_attr_list_ref)

        for fulltext_attr in fulltext_attr_list_ref:
            if fulltext_attr in g_access_requires_holdings_attribute_values:
                holdings_qualified_attr_list.append(fulltext_attr)
                unqualified_attr_list.remove(fulltext_attr)

        unqualified_string = ""
        if unqualified_attr_list:
            unqualified_string = "(rights:(" + "+OR+".join(unqualified_attr_list) + "))"

        holdings_qualified_string = ""
        inst = C.get_object("Auth").get_institution_code(C, "mapped")
        if inst:
            qualified_OR_clauses = []
            access_type = get_access_type_determination(C)

            for attr in holdings_qualified_attr_list:
                if (
                    access_type != SSD_USER
                    and attr == g_access_requires_brittle_holdings_attribute_value
                ):
                    qualified_OR_clauses.append(
                        "(ht_heldby_brlm:" + inst + "+AND+rights:" + attr + ")"
                    )
                else:
                    qualified_OR_clauses.append(
                        "(ht_heldby:" + inst + "+AND+rights:" + attr + ")"
                    )

            holdings_qualified_string = "(" + "+OR+".join(qualified_OR_clauses) + ")"

        fulltext_FQ_string = (
            "("
            + unqualified_string
            + ("+OR+" + holdings_qualified_string if holdings_qualified_string else "")
            + ")"
        )

        if self.__now_in_date_range_new_years(C):
            new_years_pd_Q_string = self.__get_new_years_pd_Q_string(C)
            fulltext_FQ_string = (
                "("
                + unqualified_string
                + (
                    "+OR+" + holdings_qualified_string
                    if holdings_qualified_string
                    else ""
                )
                + "+OR+"
                + new_years_pd_Q_string
                + ")"
            )

        return fulltext_FQ_string

    def __now_in_date_range_new_years(self, C):
        config = C.get_object("MdpConfig")
        pd_check_start_date = config.get("pd_check_start_date")
        pd_check_end_date = config.get("pd_check_end_date")
        pd_start_time = datetime.datetime(*map(int, pd_check_start_date.split("-")))
        pd_end_time = datetime.datetime(*map(int, pd_check_end_date.split("-")))
        now_time = datetime.datetime.now()
        return pd_start_time <= now_time < pd_end_time

    def __get_new_years_pd_Q_string(self, C):
        config = C.get_object("MdpConfig")
        new_years_pd_coll_id = config.get("new_years_pd_coll_id")
        solr_query = "coll_id:" + new_years_pd_coll_id

        return solr_query


if __name__ == "__main__":
    # Example usage
    query_string = "Natural history"
    # internal = [[1, 234, 4, 456, 563456, 43563, 3456345634]]
    Q = HTSearchQuery(config_query="all")
    solr_query = Q.make_solr_query(query_string=query_string, operator="OR")

    print(solr_query)
