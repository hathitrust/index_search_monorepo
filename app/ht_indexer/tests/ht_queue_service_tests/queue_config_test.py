from pathlib import Path
from typing import Any

import pytest
import yaml
from ht_queue_service.queue_config import DEFAULT_MAX_MESSAGE_SIZE_BYTES, QueueConfig


def _write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _base_global_config() -> dict[str, Any]:
    return {
        "queue": {
            "heartbeat": 60,
            "connection_timeout": 10,
        }
    }


def _base_app_config(**overrides: Any) -> dict[str, Any]:
    queue: dict[str, Any] = {
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
    queue.update(overrides)
    return {"queue": queue}


@pytest.fixture
def global_config_path(tmp_path: Path) -> Path:
    return _write_yaml(tmp_path / "global.yml", _base_global_config())


@pytest.fixture
def app_config_path(tmp_path: Path) -> Path:
    return _write_yaml(tmp_path / "app.yml", _base_app_config())


def test_derives_exchange_and_dlx_names_from_queue_name(
    global_config_path: Path, app_config_path: Path
) -> None:
    params = QueueConfig(global_config_path, app_config_path).get_params()

    assert params.main_exchange_name == "my_queue_exchange"
    assert params.dlx_exchange == "my_queue_dlx_exchange"
    assert params.dlx_routing_key == "dlx_key_my_queue"
    assert params.dlx_queue_name == "my_queue_dlq"
    assert params.arguments == {
        "x-dead-letter-exchange": "my_queue_dlx_exchange",
        "x-dead-letter-routing-key": "dlx_key_my_queue",
    }


def test_custom_arguments_override_generated_dlx_arguments(tmp_path: Path) -> None:
    global_path = _write_yaml(tmp_path / "global.yml", _base_global_config())
    app_path = _write_yaml(tmp_path / "app.yml", _base_app_config(arguments={"x-custom": "value"}))

    params = QueueConfig(global_path, app_path).get_params()

    assert params.arguments == {"x-custom": "value"}


def test_env_var_overrides_config_file_value(
    global_config_path: Path, app_config_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RABBITMQ_INDEXER_RW_HOST", "env-host")

    params = QueueConfig(global_config_path, app_config_path).get_params()

    assert params.host == "env-host"


def test_env_var_port_is_converted_to_int(
    global_config_path: Path, app_config_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RABBITMQ_INDEXER_RW_PORT", "1234")

    params = QueueConfig(global_config_path, app_config_path).get_params()

    assert params.port == 1234
    assert isinstance(params.port, int)


@pytest.fixture
def src_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RABBITMQ_INDEXER_SRC_RW_HOST", "src-env-host")
    monkeypatch.setenv("RABBITMQ_INDEXER_SRC_RW_PORT", "5672")
    monkeypatch.setenv("RABBITMQ_INDEXER_SRC_RW_USERNAME", "src-user")
    monkeypatch.setenv("RABBITMQ_INDEXER_SRC_RW_PASSWORD", "src-pass")


def test_prefixed_env_var_is_used_when_prefix_given(
    global_config_path: Path,
    app_config_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    src_config_env: None,
) -> None:

    params = QueueConfig(global_config_path, app_config_path, prefix="SRC_").get_params()

    assert params.host == "src-env-host"


def test_unprefixed_env_var_is_ignored_when_prefix_given(
    global_config_path: Path,
    app_config_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    src_config_env: None,
) -> None:
    monkeypatch.setenv("RABBITMQ_INDEXER_RW_HOST", "unprefixed-env-host")

    params = QueueConfig(global_config_path, app_config_path, prefix="SRC_").get_params()

    # The unprefixed QUEUE_HOST env var must not leak into a SRC_-prefixed config.
    assert params.host == "src-env-host"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        pytest.param({}, DEFAULT_MAX_MESSAGE_SIZE_BYTES, id="missing-uses-default"),
        pytest.param({"max_message_size": 1000}, 1000, id="from-app-config"),
    ],
)
def test_max_message_size_resolves_from_app_config(
    tmp_path: Path,
    global_config_path: Path,
    overrides: dict[str, Any],
    expected: int,
) -> None:
    """Test that max_message_size resolves correctly from the app config or uses the default."""
    app_path = _write_yaml(tmp_path / "app.yml", _base_app_config(**overrides))

    params = QueueConfig(global_config_path, app_path).get_params()

    assert params.max_message_size == expected


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        pytest.param(
            "max_message_size",
            0,
            "max_message_size must be between 1 and 536870912 bytes, got 0",
            id="max-message-size-zero",
        ),
        pytest.param(
            "max_message_size",
            536_870_913,
            "max_message_size must be between 1 and 536870912 bytes, got 536870913",
            id="max-message-size-above-rabbitmq-max",
        ),
        pytest.param(
            "batch_size", 0, "batch_size must be between 1 and 65535, got 0", id="batch-size-zero"
        ),
        pytest.param(
            "batch_size",
            65_536,
            "batch_size must be between 1 and 65535, got 65536",
            id="batch-size-above-amqp-max",
        ),
    ],
)
def test_queue_params_out_of_range_raises_value_error(
    tmp_path: Path, global_config_path: Path, field: str, value: int, message: str
) -> None:
    """Test that QueueConfig raises a ValueError when a parameter is out of the valid range."""
    app_path = _write_yaml(tmp_path / "app.yml", _base_app_config(**{field: value}))

    with pytest.raises(ValueError, match=message):
        QueueConfig(global_config_path, app_path)
