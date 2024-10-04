import config_search

from ht_full_text_search.ht_full_text_searcher import HTFullTextSearcher


class TestHTFullTextSearcher:
    def test_search(self, ht_full_text_query):
        searcher = HTFullTextSearcher(
            solr_url=config_search.SOLR_URL["dev"],
            ht_search_query=ht_full_text_query,
            user="solr",
            password="solrRocks"
        )
        solr_results = searcher.solr_result_query_dict(
            query_string="majority of the votes",
            fl=["author", "id", "title"],
            operator="AND",
        )

        for result in solr_results:
            assert "author" in result["response"]["docs"]
            assert "id" in result["response"]["docs"]
            assert "title" in result["response"]["docs"]
            assert result["response"]["numFound"] > 1

