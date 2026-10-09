import pytest
from ht_utils.ht_env_config import HtEnvConfig, HtEnvConfigMissingError


class TestHTEnvConfig:
    def test_returns_env_var(self) -> None:
        assert HtEnvConfig().solr_user == "admin"

    def test_raises_error_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MYSQL_HT_RO_PASSWORD", raising=False)

        with pytest.raises(HtEnvConfigMissingError, match="MYSQL_HT_RO_PASSWORD"):
            _ = HtEnvConfig().mysql_ht_ro_password
