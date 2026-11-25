import pytest
from ht_utils.ht_env_config import HtEnvConfig
from pydantic import ValidationError


class TestHTEnvConfig:
    def test_returns_env_var(self) -> None:
        assert HtEnvConfig().solr_full_text_ro.username == "admin"

    @pytest.mark.parametrize(
        ("var", "validation_error"),
        [
            pytest.param("MYSQL_HT_RO_PASSWORD", "mysql_ht_ro.password"),
            pytest.param("MYSQL_HT_RO_USERNAME", "mysql_ht_ro.username"),
        ],
    )
    def test_raises_error_when_missing(
        self, var: str, validation_error: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(var, raising=False)

        with pytest.raises(ValidationError, match=validation_error):
            HtEnvConfig()

    @pytest.mark.parametrize(
        ("var", "validation_error"),
        [
            pytest.param("MYSQL_HT_RO_PASSWORD", "mysql_ht_ro.password"),
            pytest.param("MYSQL_HT_RO_USERNAME", "mysql_ht_ro.username"),
        ],
    )
    def test_raises_error_when_empty(
        self, var: str, validation_error: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(var, "")

        with pytest.raises(ValidationError, match=validation_error):
            HtEnvConfig()

    def test_empty_solr_creds_return_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SOLR_CATALOG_RO_USERNAME", "")
        monkeypatch.setenv("SOLR_CATALOG_RO_PASSWORD", "")

        config = HtEnvConfig()

        assert config.solr_catalog_ro.username is None
        assert config.solr_catalog_ro.password is None

    def test_set_solr_creds_return_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SOLR_CATALOG_RO_USERNAME", "solruser")
        monkeypatch.setenv("SOLR_CATALOG_RO_PASSWORD", "solrpass")

        config = HtEnvConfig()

        assert config.solr_catalog_ro.username == "solruser"
        assert config.solr_catalog_ro.password is not None
        assert config.solr_catalog_ro.password.get_secret_value() == "solrpass"
