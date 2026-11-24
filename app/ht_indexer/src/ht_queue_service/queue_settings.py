from typing import Any, Self

from pydantic import Field, NonNegativeInt, PositiveInt, SecretStr, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, YamlConfigSettingsSource

# Used when the app config has no max_message_size: 64 MiB (67,108,864 bytes). It must not exceed the
# broker's limit (128 MiB default on RabbitMQ 3.13, 16 MiB on 4.x, which must be raised in rabbitmq.conf).
DEFAULT_MAX_MESSAGE_SIZE_BYTES = 67_108_864  # 64 MiB
RABBITMQ_MAX_MESSAGE_SIZE_BYTES = 536_870_912  # RabbitMQ hard maximum (512 MiB)
# batch_size is also passed to basic_qos as prefetch_count, a 16-bit AMQP field (0 would mean unlimited).
MAX_BATCH_SIZE = 65_535
DEFAULT_MAX_RETRIES = 5


class QueueSettings(BaseSettings):
    """Marshalls configuration from the environment and from YAML files to create connection parameters for rabbitmq"""

    host: str = Field(alias="rabbitmq_ht_indexer_host", min_length=1)
    username: str = Field(alias="rabbitmq_ht_indexer_username", min_length=1)
    password: SecretStr = Field(alias="rabbitmq_ht_indexer_password", min_length=1)
    # Parameters defining by each application
    queue_name: str = Field(min_length=1)
    batch_size: PositiveInt = Field(le=MAX_BATCH_SIZE)
    requeue_message: bool
    exchange_type: str = Field(min_length=1)
    durable: bool
    auto_delete: bool
    exclusive: bool
    heartbeat: NonNegativeInt
    connection_timeout: NonNegativeInt
    retry_interval: NonNegativeInt
    shutdown_on_empty_queue: bool

    # defaults to computed from other provided values
    main_exchange_name: str = Field(default_factory=lambda d: d["queue_name"] + "_exchange")
    dlx_exchange: str = Field(default_factory=lambda d: d["queue_name"] + "_dlx_exchange")
    dlx_routing_key: str = Field(default_factory=lambda d: "dlx_key_" + d["queue_name"])
    dlx_queue_name: str = Field(default_factory=lambda d: d["queue_name"] + "_dlq")
    arguments: dict[str, Any] = Field(default_factory=lambda: dict())

    @model_validator(mode="after")
    def merge_argument_defaults(self) -> Self:
        if "x-dead-letter-exchange" not in self.arguments:
            self.arguments["x-dead-letter-exchange"] = self.dlx_exchange

        if "x-dead-letter-routing-key" not in self.arguments:
            self.arguments["x-dead-letter-routing-key"] = self.dlx_routing_key

        return self

    # Used by the document indexer: how many times a message may be put back on the queue after
    # Solr answers its own request with a 5xx, before it is sent to the Dead Letter Queue.
    max_retries: NonNegativeInt = DEFAULT_MAX_RETRIES
    max_message_size: PositiveInt = Field(
        le=RABBITMQ_MAX_MESSAGE_SIZE_BYTES, default=DEFAULT_MAX_MESSAGE_SIZE_BYTES
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
        )
