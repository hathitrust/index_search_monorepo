from ht_full_text_search import config_search
import os

from ht_full_text_search.ht_full_text_searcher import HTFullTextSearcher


class TestHTFullTextSearcher:
    def test_search(self, ht_full_text_query):
        searcher = HTFullTextSearcher(
            solr_url=config_search.FULL_TEXT_SOLR_URL["dev"],
            ht_search_query=ht_full_text_query,
            user=os.getenv("SOLR_USER"),
            password=os.getenv("SOLR_PASSWORD")
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

