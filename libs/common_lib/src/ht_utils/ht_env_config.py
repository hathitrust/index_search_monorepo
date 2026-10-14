import os

# from functools import property


class HtEnvConfigMissingError(RuntimeError):
    """Raised when a required env var is missing.

    Environment variables must be supplied explicitly rather than silently
    defaulted. A missing credential should fail as early in the process as
    possible.
    """


class HtEnvConfig:
    """Singleton object for configuration as defined by environment variables.

    This gives a single place to define what environment variables are used, to
    fetch them when needed, and to usefully report errors when missing.
    """

    instance = None

    @property
    def rabbitmq_indexer_rw_host(self) -> str:
        return self._env("RABBITMQ_INDEXER_RW_HOST")

    @property
    def rabbitmq_indexer_rw_port(self) -> str:
        return self._env("RABBITMQ_INDEXER_RW_PORT")

    @property
    def rabbitmq_indexer_rw_username(self) -> str:
        return self._env("RABBITMQ_INDEXER_RW_USERNAME")

    @property
    def rabbitmq_indexer_rw_password(self) -> str:
        return self._env("RABBITMQ_INDEXER_RW_PASSWORD")

    @property
    def rabbitmq_indexer_src_rw_host(self) -> str:
        return self._env("RABBITMQ_INDEXER_SRC_RW_HOST")

    @property
    def rabbitmq_indexer_src_rw_port(self) -> str:
        return self._env("RABBITMQ_INDEXER_SRC_RW_PORT")

    @property
    def rabbitmq_indexer_src_rw_username(self) -> str:
        return self._env("RABBITMQ_INDEXER_SRC_RW_USERNAME")

    @property
    def rabbitmq_indexer_src_rw_password(self) -> str:
        return self._env("RABBITMQ_INDEXER_SRC_RW_PASSWORD")

    @property
    def rabbitmq_indexer_tgt_rw_host(self) -> str:
        return self._env("RABBITMQ_INDEXER_TGT_RW_HOST")

    @property
    def rabbitmq_indexer_tgt_rw_port(self) -> str:
        return self._env("RABBITMQ_INDEXER_TGT_RW_PORT")

    @property
    def rabbitmq_indexer_tgt_rw_username(self) -> str:
        return self._env("RABBITMQ_INDEXER_TGT_RW_USERNAME")

    @property
    def rabbitmq_indexer_tgt_rw_password(self) -> str:
        return self._env("RABBITMQ_INDEXER_TGT_RW_PASSWORD")

    @property
    def mysql_ht_ro_host(self) -> str:
        return self._env("MYSQL_HT_RO_HOST")

    @property
    def mysql_ht_ro_port(self) -> str:
        return self._env("MYSQL_HT_RO_PORT")

    @property
    def mysql_ht_ro_username(self) -> str:
        return self._env("MYSQL_HT_RO_USERNAME")

    @property
    def mysql_ht_ro_password(self) -> str:
        return self._env("MYSQL_HT_RO_PASSWORD")

    @property
    def mysql_ht_ro_database(self) -> str:
        return self._env("MYSQL_HT_RO_DATABASE")

    @property
    def full_text_solr_ro_url(self) -> str:
        return self._env("FULL_TEXT_SOLR_RO_URL")

    @property
    def catalog_solr_ro_url(self) -> str:
        return self._env("CATALOG_SOLR_RO_URL")

    @property
    def solr_user(self) -> str:
        return self._env("SOLR_USER")

    @property
    def solr_password(self) -> str:
        return self._env("SOLR_PASSWORD")

    @property
    def sdr_dir(self) -> str:
        return self._env("SDR_DIR")

    def __new__(cls) -> HtEnvConfig:
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def _env(self, var: str) -> str:
        val = os.getenv(var)
        if not val:
            raise HtEnvConfigMissingError(f"{var} env var required")
        return val
