from ht_search.config_search import DEFAULT_SOLR_PARAMS, default_solr_params


class TestDefaultSolrParams:
    """default_solr_params() used to return a reference to the shared module-level
    DEFAULT_SOLR_PARAMS dict. Callers (e.g. SolrExporter.run_cursor) mutate the dict they get
    back with per-query values like 'q' and 'cursorMark', so a second call in the same process
    inherited the first call's query and a stale cursor."""

    def test_returns_a_fresh_dict_each_call(self):
        first = default_solr_params(env="dev")
        first["q"] = "title:first query"
        first["cursorMark"] = "some-cursor-value"

        second = default_solr_params(env="dev")

        assert second is not first
        assert "q" not in second
        assert "cursorMark" not in second

    def test_does_not_mutate_the_module_level_default(self):
        params = default_solr_params(env="prod")
        params["q"] = "title:another query"

        assert "q" not in DEFAULT_SOLR_PARAMS
        assert "shards" not in DEFAULT_SOLR_PARAMS

    def test_prod_env_adds_shards_to_the_returned_copy_only(self):
        params = default_solr_params(env="prod")

        assert "shards" in params
        assert "shards" not in DEFAULT_SOLR_PARAMS

    def test_dev_env_does_not_add_shards(self):
        params = default_solr_params(env="dev")

        assert "shards" not in params
