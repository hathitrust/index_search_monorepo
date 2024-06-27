import requests
import json
from ht_query.ht_query import HTSearchQuery
from typing import Text, List, Dict

from config_search import SOLR_URL


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

    def __init__(
        self,
        engine_uri: Text = None,
        timeout: int = None,
        ht_search_query: HTSearchQuery = None,
        use_shards: bool = False,
    ):
        self.engine_uri = engine_uri
        self.timeout = timeout
        self.use_shards = use_shards  # Not sure if we need it right now
        self.query_maker = ht_search_query

        # TODO HTTP request string and JSON object. We should transform the query string into a JSON object
        self.headers = {
            "Content-type": "application/json"
        }  # { "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}

    def get_Solr_raw_internal_query_result(self, C, url):
        return self.solr_result_query_dict(C, url)

    def get_documents_query_string(self):

        pass

    def solr_result_query_string(self, url, str_query: Text = None, fl: List = None, operator: Text = None, list_filters: List = None):

        query_string = self.query_maker.manage_string_query_solr6(str_query, operator=operator)

        #for q in ["\"Culture in History: Essays in Honor of Paul Radin\"", "Culture OR in OR History: OR Essays OR in OR Honor OR of OR Paul OR Radin", "Culture AND in AND History: AND Essays AND in AND Honor AND of AND Paul AND Radin"]:
        #    print('**********')
        #    print(q)
        #    str_query = q#"Culture in History: Essays in Honor of Paul Radin"

        ids_strings = "\" \"".join(list_filters)  # "inu.30000053396481 wu.89071558118"

        print(ids_strings)  # &mm=100%

        self.query_maker.query_filter_creator_string('id', ids_strings)

        if self.use_shards:
            shards = f"shards={self.use_shards}"
            solr_query = f'{url}select?defType=edismax&{shards}&mm=100%&fq=id:(\"{ids_strings}\")&indent=on&mm=100%&q={query_string}&fl=author,id,title&qf=ocr&wt=json'
        else:
            solr_query = f'{url}select?defType=edismax&mm=100%&fq=id:(\"{ids_strings}\")&indent=on&mm=100%&q={query_string}&fl=author,id,title&qf=ocr&wt=json'

        print(solr_query)
        #    shards = "shards=solr-sdr-search-1:8081/solr/core-1x,solr-sdr-search-2:8081/solr/core-2x,solr-sdr-search-3:8081/solr/core-3x,solr-sdr-search-4:8081/solr/core-4x,solr-sdr-search-5:8081/solr/core-5x,solr-sdr-search-6:8081/solr/core-6x,solr-sdr-search-7:8081/solr/core-7x,solr-sdr-search-8:8081/solr/core-8x,solr-sdr-search-9:8081/solr/core-9x,solr-sdr-search-10:8081/solr/core-10x,solr-sdr-search-11:8081/solr/core-11x,solr-sdr-search-12:8081/solr/core-12x"
        #list_ids = ["inu.30000053396481", "wu.89071558118"]  #list_filters


        #response = requests.get(
        #        f'http://beeftea-1.umdl.umich.edu:8091/solr/core-2x/select?defType=edismax&{shards}&mm=100%&fq=id:({ids_strings})&indent=on&q={str_query}&fl=author,id,title&qf=ocr&wt=json')
        #response = requests.get(solr_query, stream=True)

        joining_solr_output = {}
        for query_response in self.get_documents_query_string(None, None,None, method="GET", solr_query=solr_query):
            # rs.ingest_solr_search_response(code, response, status_line, failed_HTTP_dump)
            print(query_response["content"])
            solr_output = json.loads(query_response["content"])

            joining_solr_output.update(solr_output)
        return joining_solr_output

        """
        content = ""
        if response.content:
            content = response.content.decode("utf-8")

        result = {
            "code": response.status_code,
            "content": content,
            "status": response.reason
        }
                #print(content)
        solr_output = json.loads(result['content'])
        print(solr_output['response']['numFound'])
        return solr_output
        """

    def get_documents_query_dict(self, url, query_dict, start: int = 0, rows: int = 100):

        #response_content = []  # contains partial or full page_source

        #if method == "GET":
        #    response = requests.get(solr_query, stream=True)
        #else:
            # req = requests.get(url=url, params=query_dict, headers=self.headers)
        print(url)
        print(f"{url.replace('#/', '')}query")
        query_dict.update({"start": start, "rows": rows})
        response = requests.post(
                url=f"{url.replace('#/', '')}query", params=query_dict, headers=self.headers, stream=True
            )
        return response
    def solr_result_query_dict(
        self, url, query_string: Text = None, fl: List = None, operator: Text = None, query_filter: bool = False,
            filter_dict: Dict = None, rows: int = 100, start: int = 0):
        """

        :param filter_dict:
        :param operator:
        :param query_filter:
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
            query_string=query_string, operator=operator, fl=fl, query_filter=query_filter, filter_dict=filter_dict
        )

        if self.use_shards:
            query_dict["shards"] = self.use_shards
            query_dict["shards.info"] = "true"
        print(query_dict)

        query_dict.update({"start": start, "rows": rows})

        #Counting total records
        response = self.get_documents_query_dict(url, query_dict)
        output = response.json()

        try:
            total_records = output.get("response").get("numFound")
            print(total_records)
        except Exception as e:
            print(f"Solr index {url} seems empty {e}")
            exit()
        count_records = 0
        while count_records < total_records:
            results = []

            response = self.get_documents_query_dict(url, query_dict, start, rows)

            output = json.loads(response.content.decode("utf-8"))

            count_records = count_records + len(output.get("response").get("docs"))

            print(f"Batch documents {count_records}")
            start += rows
            print(f"Result length {len(results)}")
            yield output
        """
        
        
        joining_solr_output = {}
        for query_response in self.get_documents_query_string(ua, url, query_dict):

            # rs.ingest_solr_search_response(code, response, status_line, failed_HTTP_dump)
            print(query_response["content"])
            solr_output = json.loads(query_response["content"])

            joining_solr_output.update(solr_output)
        return joining_solr_output
        """




        # res = ua.request(req)



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
    """