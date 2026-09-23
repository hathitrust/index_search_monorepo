from pathlib import Path
from typing import Any

import pytest
import yaml
from ht_queue_service.queue_config import QueueConfig

# The docker compose test environment sets these for the real queue services
# (e.g. QUEUE_HOST=rabbitmq), so every test here must start from a clean slate or
# it ends up asserting against real broker config instead of the YAML fixtures.
_QUEUE_ENV_VARS = [
    f"{prefix}QUEUE_{suffix}"
    for prefix in ("", "SRC_", "TGT_")
    for suffix in ("HOST", "PORT", "USER", "PASS", "NAME")
]


@pytest.fixture(autouse=True)
def clean_queue_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _QUEUE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _base_global_config() -> dict[str, Any]:
    return {
        "queue": {
            "host": "global-host",
            "port": 5672,
            "user": "global-user",
            "password": "global-pass",
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
        "heartbeat": 60,
        "connection_timeout": 10,
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


def test_loads_connection_fields_from_global_and_queue_fields_from_app_config(
    global_config_path: Path, app_config_path: Path
) -> None:
    params = QueueConfig(global_config_path, app_config_path).get_params()

    assert params.host == "global-host"
    assert params.port == 5672
    assert params.user == "global-user"
    assert params.password == "global-pass"
    assert params.queue_name == "my_queue"
    assert params.batch_size == 10


def test_app_config_takes_precedence_over_global_config(tmp_path: Path) -> None:
    global_path = _write_yaml(tmp_path / "global.yml", _base_global_config())
    app_path = _write_yaml(tmp_path / "app.yml", _base_app_config(host="app-host"))

    params = QueueConfig(global_path, app_path).get_params()

    assert params.host == "app-host"


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
    monkeypatch.setenv("QUEUE_HOST", "env-host")

    params = QueueConfig(global_config_path, app_config_path).get_params()

    assert params.host == "env-host"


def test_env_var_port_is_converted_to_int(
    global_config_path: Path, app_config_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QUEUE_PORT", "1234")

    params = QueueConfig(global_config_path, app_config_path).get_params()

    assert params.port == 1234
    assert isinstance(params.port, int)


def test_prefixed_env_var_is_used_when_prefix_given(
    global_config_path: Path, app_config_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SRC_QUEUE_HOST", "src-env-host")

    params = QueueConfig(global_config_path, app_config_path, prefix="SRC_").get_params()

    assert params.host == "src-env-host"


def test_unprefixed_env_var_is_ignored_when_prefix_given(
    global_config_path: Path, app_config_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QUEUE_HOST", "unprefixed-env-host")

    params = QueueConfig(global_config_path, app_config_path, prefix="SRC_").get_params()

    # The unprefixed QUEUE_HOST env var must not leak into a SRC_-prefixed config.
    assert params.host == "global-host"
