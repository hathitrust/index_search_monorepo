from pathlib import Path
from typing import Any

import pytest
import yaml
from ht_queue_service.queue_settings import QueueSettings
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict


class QueueTestSettingsFromYaml(QueueSettings):
    model_config = SettingsConfigDict(
        env_prefix="RABBITMQ_TEST_",
    )

    # dynamically define yaml path at instantiation
    def __init__(self, yaml_path: Path, **kwargs: Any):
        self.model_config["yaml_file"] = yaml_path
        super().__init__(**kwargs)


def _write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _base_app_config(**overrides: Any) -> dict[str, Any]:
    config = {
        "heartbeat": 60,
        "connection_timeout": 10,
        "queue_name": "my_queue",
        "batch_size": 10,
        "requeue_message": False,
        "exchange_type": "direct",
        "durable": True,
        "auto_delete": False,
        "exclusive": False,
        "retry_interval": 5,
        "shutdown_on_empty_queue": False,
    }
    config.update(overrides)
    return config


@pytest.fixture
def yaml_path(tmp_path: Path) -> Path:
    return _write_yaml(tmp_path / "app.yml", _base_app_config())


def test_derives_exchange_and_dlx_names_from_queue_name(yaml_path: Path) -> None:

    settings = QueueTestSettingsFromYaml(yaml_path)

    assert settings.main_exchange_name == "my_queue_exchange"
    assert settings.dlx_exchange == "my_queue_dlx_exchange"
    assert settings.dlx_routing_key == "dlx_key_my_queue"
    assert settings.dlx_queue_name == "my_queue_dlq"
    assert settings.arguments == {
        "x-dead-letter-exchange": "my_queue_dlx_exchange",
        "x-dead-letter-routing-key": "dlx_key_my_queue",
    }


def test_provided_dlx_arguments_override_defaults(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path / "app.yml",
        _base_app_config(arguments={"x-dead-letter-exchange": "somethingelse"}),
    )
    settings = QueueTestSettingsFromYaml(yaml_path)

    assert settings.arguments == {
        "x-dead-letter-exchange": "somethingelse",
        "x-dead-letter-routing-key": "dlx_key_my_queue",
    }


def test_custom_arguments_merge_with_dlx_arguments(tmp_path: Path) -> None:
    yaml_path = _write_yaml(tmp_path / "app.yml", _base_app_config(arguments={"x-custom": "value"}))
    settings = QueueTestSettingsFromYaml(yaml_path)

    assert settings.arguments == {
        "x-custom": "value",
        "x-dead-letter-exchange": "my_queue_dlx_exchange",
        "x-dead-letter-routing-key": "dlx_key_my_queue",
    }


def test_env_var_overrides_config_file_value(
    yaml_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RABBITMQ_TEST_QUEUE_NAME", "env-some-other-queue")

    settings = QueueTestSettingsFromYaml(yaml_path)

    assert settings.queue_name == "env-some-other-queue"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        pytest.param(
            "max_message_size",
            0,
            "greater than 0",
            id="max-message-size-zero",
        ),
        pytest.param(
            "max_message_size",
            536_870_913,
            "less than or equal to 536870912",
            id="max-message-size-above-rabbitmq-max",
        ),
        pytest.param("batch_size", 0, "greater than 0", id="batch-size-zero"),
        pytest.param(
            "batch_size",
            65_536,
            "less than or equal to 65535",
            id="batch-size-above-amqp-max",
        ),
    ],
)
def test_queue_params_out_of_range_raises_value_error(
    yaml_path: Path, field: str, value: int, message: str
) -> None:
    """Test that QueueSettings raises a ValidationError when a parameter is out of the valid range."""

    with pytest.raises(ValidationError, match=message):
        QueueTestSettingsFromYaml(yaml_path, **{field: value})
