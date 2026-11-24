from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SolrConnectionParameters(BaseModel):
    @staticmethod
    def remove_empty(value: str | None) -> str | None:
        return value if value else None

    url: str = Field(min_length=1)
    username: Annotated[str | None, AfterValidator(remove_empty)] = None
    password: Annotated[SecretStr | None, AfterValidator(remove_empty)] = None


class MysqlConnectionParameters(BaseModel):
    host: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)
    database: str = Field(min_length=1)


class HtEnvConfig(BaseSettings):
    """Object for configuration as defined by environment variables.

    This gives a single place to define what environment variables are used, to
    fetch them when needed, and to usefully report errors when missing.
    """

    model_config = SettingsConfigDict(
        env_nested_delimiter="_", nested_model_default_partial_update=True
    )

    log_level: str = "INFO"
    sdr_dir: str | None = None

    # TODO: Raise something more useful if these aren't set?
    mysql_ht_ro: MysqlConnectionParameters

    solr_catalog_ro: SolrConnectionParameters
    solr_full_text_ro: SolrConnectionParameters
    solr_full_text_rw: SolrConnectionParameters
