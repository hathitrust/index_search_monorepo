import os
from unittest.mock import patch

from ht_full_text_search.ht_full_text_searcher import HTFullTextSearcher
from ht_search import config_search


class TestRetrieveDocumentsFromFile:
    """retrieve_documents_from_file's batching loop used to live entirely inside
    `if len(list_ids) > 100:`, so a list of 100 or fewer ids silently yielded nothing instead
    of one batch."""

    @staticmethod
    def _searcher():
        return HTFullTextSearcher(solr_url="http://fake-solr", ht_search_query=None, environment="dev")

    def test_yields_a_batch_for_100_or_fewer_ids(self):
        searcher = self._searcher()
        list_ids = [f"id_{i}" for i in range(50)]

        with patch.object(searcher, "solr_result_output", return_value=(["doc"], ["debug"])) as mock_output:
            batches = list(searcher.retrieve_documents_from_file(list_ids=list_ids))

        assert batches == [(["doc"], ["debug"])]
        mock_output.assert_called_once()
        assert mock_output.call_args.kwargs["filter_dict"] == {"id": list_ids}

    def test_yields_multiple_batches_over_100_ids(self):
        searcher = self._searcher()
        list_ids = [f"id_{i}" for i in range(150)]

        with patch.object(searcher, "solr_result_output", return_value=(["doc"], ["debug"])) as mock_output:
            batches = list(searcher.retrieve_documents_from_file(list_ids=list_ids))

        assert len(batches) == 2
        first_chunk = mock_output.call_args_list[0].kwargs["filter_dict"]["id"]
        second_chunk = mock_output.call_args_list[1].kwargs["filter_dict"]["id"]
        assert len(first_chunk) == 100
        assert len(second_chunk) == 50

    def test_empty_list_yields_nothing(self):
        assert list(self._searcher().retrieve_documents_from_file(list_ids=[])) == []

    def test_none_list_yields_nothing(self):
        assert list(self._searcher().retrieve_documents_from_file(list_ids=None)) == []


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

