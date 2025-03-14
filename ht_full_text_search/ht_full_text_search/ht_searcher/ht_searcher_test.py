import pytest
import os

from ht_full_text_search import config_search
from ht_full_text_search.ht_searcher.ht_searcher import HTSearcher

"""
{"responseHeader":{"zkConnected":true,"status":0,"QTime":3,"params":{"q":"*:*","indent":"off","fl":"id","start":"0","json":"","rows":"10","wt":"json"}},
"response":{"numFound":1978,"start":0,"numFoundExact":true,
"docs":[{"id":"umn.31951d000486952"},
{"id":"umn.31951002376334b"},
{"id":"mdp.39015041533723"},
{"id":"mdp.39015064899100"},
{"id":"umn.31951001993406h"},
{"id":"mdp.39015086530709"},
{"id":"umn.319510023514380"},
{"id":"umn.319510022616074"},
{"id":"nyp.33433079722553"},
{"id":"wu.89064210685"}]}}
"""

"""
{"responseHeader":{"status":0,"QTime":22,"params":{"q":"*:*","indent":"off","fl":"id","start":"0","json":"","rows":"10","wt":"json"}},"response":{"numFound":1978,"start":0,
"docs":[{"id":"umn.31951d000486952"},
{"id":"umn.31951002376334b"},
{"id":"mdp.39015041533723"},
{"id":"mdp.39015064899100"},
{"id":"umn.31951001993406h"},
{"id":"mdp.39015086530709"},
{"id":"umn.319510023514380"},
{"id":"umn.319510022616074"},
{"id":"nyp.33433079722553"},
{"id":"wu.89064210685"}]}}
"""

"""
title:health

solr6
"docs":[{"id":"umn.31951d027481571"},
{"id":"umn.31951002902590d"},
{"id":"umn.31951002077778r"},
{"id":"umn.31951002820042d"},
{"id":"mdp.39015005127280"},
{"id":"mdp.39015009035372"}]}}

solr8 ClassicSimilarity
"docs":[{"id":"umn.31951d027481571"},
{"id":"umn.31951002902590d"},
{"id":"umn.31951002077778r"},
{"id":"umn.31951002820042d"},
{"id":"mdp.39015005127280"},
{"id":"mdp.39015009035372"}]}}

solr8 BM25Similarity


https://localhost:8080/cgi/ls?lmt=ft&a=srchls&adv=1&q1=health&field1=ocronly&anyall1=any&op1=AND


url=http://solr-lss-dev:8983/solr/core-x?q=+_query_:"{!edismax+qf='ocr^50000+allfieldsProper^2+allfields^1+titleProper^50+title_topProper^30+title_restProper^15+title^10+title_top^5+title_rest^2+series^5+series2^5+author^80+author2^50+issn^1+isbn^1+oclc^1+sdrnum^1+ctrlnum^1+id^1+rptnum^1+topicProper^2+topic^1+hlb3^1+fullgeographic^1+fullgenre^1+era^1+'++pf='title_ab^10000+titleProper^1500+title_topProper^1000+title_restProper^800+series^100+series2^100+author^1600+author2^800+topicProper^200+fullgenre^200+hlb3^200+allfieldsProper^100+'++mm='100%25'++tie='0.9'+}+history"+&fl=title_display,title,title_c,volume_enumcron,vtitle,author,author2,mainauthor,date,rights,id,record_no,oclc,isbn,lccn,score,bothPublishDate,enumPublishDate&fq=((rights:(1+OR+24+OR+7+OR+14+OR+19+OR+22+OR+11+OR+12+OR+21+OR+15+OR+17+OR+23+OR+25+OR+13+OR+20+OR+18+OR+10)))&version=2.2&start=0&rows=0&indent=off&facet.mincount=1&facet=true&facet.limit=30&facet.field=topicStr&facet.field=authorStr&facet.field=language008_full&facet.field=countryOfPubStr&facet.field=bothPublishDateRange&facet.field=format&facet.field=htsource&wt=json&json.nl=arrarr&fq=
"""


@pytest.fixture(scope="module", autouse=True)
def ht_searcher_fixture():
    """
    Fixture that instantiates the HTSearcher class
    :return:
    """

    return HTSearcher(
        solr_url=config_search.FULL_TEXT_SOLR_URL["dev"],
        environment="dev",
        user = os.getenv("SOLR_USER"),
        password = os.getenv("SOLR_PASSWORD")
    )


class TestHTSearcher:

    def test_get_query_response(self, ht_searcher_fixture):
        # query_string = "?q=*:*&q.op=OR&indent=true"  # "indent=on&q=date:1874&wt=json"
        # query_dict = {"indent": "on", "q": {"date":"1874"}, "wt": "json"}

        query_dict = {"q": "*:*"}
        response = ht_searcher_fixture.send_query(query_dict)

        assert response.content is not None
        assert response.status_code == 200
        assert response.reason == "OK"
