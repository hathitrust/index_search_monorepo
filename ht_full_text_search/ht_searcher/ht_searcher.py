import requests
import json
from ht_query.ht_query import HTSearchQuery
from typing import Text, List


"""
Perl
slip-lib::Search::Searcher

* slip-lib::Search::Searcher
     This class encapsulates the search interface to Solr/Lucene. It
    provides two interfaces.  One to handle user entered queries and one
    to handle queries generated internally by the application.

There is a logic to select Solr URL that with Solr Cloud probably we did not need it anymore
"""


class HTSearcher:
    """
    Inputs:
        - Solr url
        - query string

    This class encapsulates the search interface to Solr.

    In perl we have an input variable C, that is the context with the main set up to initialize the search
    We should identify what is the best way of doing it in python (if need it) => it probably makes sense to
    create a JSON ir YAML file with these parameters, default query, default urls, num_documents, pagination

    """

    def __init__(self, engine_uri, timeout=None, ht_search_query: HTSearchQuery = None):
        self.engine_uri = engine_uri
        self.timeout = timeout
        self.use_ls_shards = False  # Not sure if we need it right now
        self.query_maker = ht_search_query

        # TODO HTTP request string and JSON object. We should transform the query string into a JSON object
        self.headers = {
            "Content-type": "application/json"
        }  # { "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}

    def get_Solr_raw_internal_query_result(self, C, url):
        return self.solr_result(C, url)

    def solr_result(
        self, url, query_string: Text = None, fl: List = None, operator: Text = None,
    ):
        """

        :param url:
        :param query_string:
        :param fl:
        :param query_type: It could be, all, exact_match or boolean_opperator
        :return:
        """
        # query_string += "&wt=json&indent=off" if "wt=" not in query_string else ""

        # query_dict = self.query_maker.query_string_to_dict(query_string)

        # TODO: Create user agent???
        ua = None  # __create_user_agent()

        # TODO Use case: Add a function to debug the query
        # if DEBUG('query'):
        #    d = url
        #    d = d.replace('"', '\\"').replace("'", "\\'") if under_server() else d
        #    DEBUG('query', f"Query URL: {d}")
        # query_dict = self.query_maker.make_solr_query(query_string=query_string, fl=fl)
        query_dict = self.query_maker.make_solr_query(
            query_string=query_string, operator=operator, fl=fl
        )

        query_response = self.get_query_response(ua, url, query_dict)

        # rs.ingest_solr_search_response(code, response, status_line, failed_HTTP_dump)
        print(query_response["content"])
        solr_output = json.loads(query_response["content"])

        return solr_output

    def get_query_response(self, ua, url, query_dict):
        """
        Function to get query response
        :param C:
        :param ua:
        :param url:
        :param query_string:
        :return:
        """

        # req = requests.get(url=url, params=query_dict, headers=self.headers)
        print(url)
        print(f"{url.replace('#/', '')}query")
        #response = requests.post(
        #    url=f"{url.replace('#/', '')}query", params=query_dict, headers=self.headers
        #)

        response = requests.post(
            url=f"{url}query", data=query_dict, headers=self.headers
        )

        # res = ua.request(req)

        code = response.status_code
        status_line = response.reason
        http_status_fail = not response.ok

        failed_HTTP_dump = ""
        # TODO: Implement Request failed & DEBUG
        """
        # Debug / fail logging
        responseDebug = DEBUG('response,idx,all')
        otherDebug = DEBUG('idx,all')
        Debug = responseDebug or otherDebug

        if Debug or http_status_fail:

            if otherDebug:
                u = req.url
                u = Utils.map_chars_to_cers(u)
                s = f"__get_query_response: request='{u}': status='{code}' status_line={status_line}"
                DEBUG('idx,all', s)

            if responseDebug or http_status_fail:
                d = res.text

                if http_status_fail:
                    sesion_id = 0
                    if C.has_object('Session'):
                        sesion_id = C.get_object('Session').get_session_id()
                    remote_addr = os.environ.get('REMOTE_ADDR', '0.0.0.0')
                    lg = f"{remote_addr} {sesion_id} {os.getpid()} {Utils.Time.iso_Time('time')} {d}"
                    app_name = C.get_object('App').get_app_name(C) if C.has_object('App') else 'ls'
                    Utils.Logger.__Log_string(C, lg, 'query_error_logfile', '___QUERY___', app_name)
                    failed_HTTP_dump = d

                d = Utils.map_chars_to_cers(d, ['"', "'"]) if Debug.DUtils.under_server()
                DEBUG('response', d)
        """
        content = ""

        if response.content:
            content = response.content.decode("utf-8")

        return {
            "code": code,
            "content": content,
            "status": status_line,
            "failed_HTTP_dump": failed_HTTP_dump,
        }

    """
    # TODO: we do not need this function
    def get_request_object(self, url):

        url, query_string = url.split('?')

        # Encode query string if it is UTF-8
        if isinstance(query_string, str) and not query_string.isascii():
            query_string = query_string.encode('utf-8')

        #TODO: Add basic authentication ==> See this tutorial for different ways of authentication: https://www.geeksforgeeks.org/python-requests-tutorial/
        #if C is not None:
        #    req = add_basic_auth(req, C)

        return url, query_string
    """

    """
    Function created by the model
    def add_basic_auth(req, C):
        username = C['username']
        password = C['password']

        credentials = f'{username}:{password}'.encode('utf-8')
        encoded_credentials = base64.b64encode(credentials)
        auth_header = f'Basic {encoded_credentials.decode("utf-8")}'

        req.add_header('Authorization', auth_header)

        return req
    """

    def __get_solr_select_url(self, C, query_string):
        # Add your implementation here
        pass

    def __get_request_object(self, url, C):
        # Add your implementation here
        pass

    def __create_user_agent(self):
        # Add your implementation here
        pass

    def DEBUG(sel, param):
        # Add your implementation here
        pass

    def under_server(self):
        # Add your implementation here
        pass

    class RS:
        def ingest_solr_search_response(
            self, code, response, status_line, failed_HTTP_dump
        ):
            # Add your implementation here
            pass


if __name__ == "__main__":
    # input:
    solr_url = "http://localhost:8983/solr/#/core-x/"

    query_string = "Natural history"
    fl = ["author", "id", "title"]

    # Create query object
    Q = HTSearchQuery(conf_query="all")

    ht_search = HTSearcher(solr_url, ht_search_query=Q)
    solr_output = ht_search.solr_result(
        url=solr_url, query_string=query_string, fl=fl, operator=None
    )
