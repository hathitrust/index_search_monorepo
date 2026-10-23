import pytest
from ht_utils.ht_env_config import HtEnvConfig, HtEnvConfigMissingError

CATALOG_USER = "catalog-user"
CATALOG_PASSWORD = "catalog-pass"


def _apply_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str | None]) -> None:
    for var, value in env.items():
        if value is None:
            monkeypatch.delenv(var, raising=False)
        else:
            monkeypatch.setenv(var, value)


class TestHTEnvConfig:
    @pytest.mark.parametrize(
        ("property_name", "env", "expected"),
        [
            # Required env vars - SOLR_USER is set
            pytest.param("solr_user", {"SOLR_USER": "admin"}, "admin", id="required-set"),
            # Optional env vars - both set
            pytest.param(
                "solr_catalog_ro_username",
                {
                    "SOLR_CATALOG_RO_USERNAME": CATALOG_USER,
                    "SOLR_CATALOG_RO_PASSWORD": CATALOG_PASSWORD,
                },
                CATALOG_USER,
                id="catalog-username-set",
            ),
            # Optional env vars - both unset
            pytest.param(
                "solr_catalog_ro_username",
                {"SOLR_CATALOG_RO_USERNAME": None, "SOLR_CATALOG_RO_PASSWORD": None},
                None,
                id="catalog-pair-unset",
            ),
            # Optional env vars - both empty
            pytest.param(
                "solr_catalog_ro_username",
                {"SOLR_CATALOG_RO_USERNAME": "", "SOLR_CATALOG_RO_PASSWORD": ""},
                None,
                id="catalog-pair-empty",
            ),
        ],
    )
    def test_returns_env_var(
        self,
        monkeypatch: pytest.MonkeyPatch,
        property_name: str,
        env: dict[str, str | None],
        expected: str | None,
    ) -> None:
        _apply_env(monkeypatch, env)

        value = getattr(HtEnvConfig(), property_name)

        assert value == expected

    @pytest.mark.parametrize(
        ("property_name", "env", "match"),
        [
            # Required env vars - MYSQL_HT_RO_PASSWORD is unset
            pytest.param(
                "mysql_ht_ro_password",
                {"MYSQL_HT_RO_PASSWORD": None},
                "MYSQL_HT_RO_PASSWORD",
                id="required-unset",
            ),
            # Optional env vars SOLR_CATALOG_RO_USERNAME is unset while SOLR_CATALOG_RO_PASSWORD is set
            pytest.param(
                "solr_catalog_ro_username",
                {"SOLR_CATALOG_RO_USERNAME": None, "SOLR_CATALOG_RO_PASSWORD": CATALOG_PASSWORD},
                "SOLR_CATALOG_RO_USERNAME env var required when SOLR_CATALOG_RO_PASSWORD is set",
                id="catalog-username-missing-password-set",
            ),
        ],
    )
    def test_raises_error_when_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        property_name: str,
        env: dict[str, str | None],
        match: str,
    ) -> None:
        _apply_env(monkeypatch, env)

        with pytest.raises(HtEnvConfigMissingError, match=match):
            getattr(HtEnvConfig(), property_name)
