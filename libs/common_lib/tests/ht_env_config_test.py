import pytest
from ht_utils.ht_env_config import HtEnvConfig, HtEnvConfigMissingError


class TestHTEnvConfig:
    def test_returns_env_var(self) -> None:
        assert HtEnvConfig().solr_user == "admin"

    def test_raises_error_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MYSQL_HT_RO_PASSWORD", raising=False)

        with pytest.raises(HtEnvConfigMissingError, match="MYSQL_HT_RO_PASSWORD"):
            _ = HtEnvConfig().mysql_ht_ro_password

    @pytest.mark.parametrize("var", ["SOLR_CATALOG_RO_USERNAME", "SOLR_CATALOG_RO_PASSWORD"])
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            pytest.param("secret", "secret", id="set"),
            pytest.param("", None, id="empty"),
        ],
    )
    def test_optional_env_returns_value_or_none(
        self, monkeypatch: pytest.MonkeyPatch, var: str, value: str, expected: str | None
    ) -> None:
        monkeypatch.setenv(var, value)
        result = getattr(HtEnvConfig(), var.lower())

        assert result == expected
