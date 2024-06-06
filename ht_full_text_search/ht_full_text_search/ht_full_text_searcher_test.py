import config_search

from ht_full_text_search.ht_full_text_searcher import HTFullTextSearcher


class TestHTFullTextSearcher:
    def test_search(self, ht_full_text_query):
        searcher = HTFullTextSearcher(
            engine_uri=config_search.SOLR_URL["dev"],
            ht_search_query=ht_full_text_query,
            use_shards=False,
        )
        solr_results = searcher.solr_result_query_dict(
            query_string="majority of the votes",
            fl=["author", "id", "title"],
            operator="AND",
        )
        assert solr_results["response"]["numFound"] > 1
