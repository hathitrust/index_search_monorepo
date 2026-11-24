import argparse
import sys

import pytest
import yaml
from document_indexer_service import indexer_config_file_path
from document_indexer_service.indexer_arguments import IndexerServiceArguments


def _arguments(monkeypatch: pytest.MonkeyPatch, *extra: str) -> IndexerServiceArguments:
    """Parse a command line the way the indexer does, with the real indexer_config.yml."""
    monkeypatch.setenv("SOLR_FULL_TEXT_RW_URL", "http://solr-lss-dev:8983/solr/core-x/")
    monkeypatch.setenv("SOLR_FULL_TEXT_RW_USERNAME", "solr_user")
    monkeypatch.setenv("SOLR_FULL_TEXT_RW_PASSWORD", "solr_password")
    monkeypatch.setattr(sys, "argv", ["indexer", *extra])
    return IndexerServiceArguments(argparse.ArgumentParser())


def _configured_batch_size() -> int:
    config_file = indexer_config_file_path / "indexer_config.yml"
    batch_size: int = yaml.safe_load(config_file.read_text())["queue"]["batch_size"]
    return batch_size


def test_batch_size_on_the_command_line_overrides_indexer_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(monkeypatch, "--batch_size", "25")

    assert arguments.queue_settings.batch_size == 25
    assert arguments.queue_settings.batch_size != _configured_batch_size()


def test_without_batch_size_the_value_from_indexer_config_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(monkeypatch)

    assert arguments.queue_settings.batch_size == _configured_batch_size()


@pytest.mark.parametrize("value", ["0", "65536"])
def test_batch_size_out_of_range_exits_with_an_error(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        _arguments(monkeypatch, "--batch_size", value)

    assert exit_info.value.code == 1


def test_batch_size_must_be_a_number(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as exit_info:
        _arguments(monkeypatch, "--batch_size", "many")

    assert exit_info.value.code == 2  # argparse's own exit code for a bad value


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        pytest.param([], (60.0, 120.0), id="default"),
        pytest.param(
            ["--solr_timeout", "30"], (60.0, 30.0), id="read-timeout-from-the-command-line"
        ),
        pytest.param(
            ["--solr_connect_timeout", "90"],
            (90.0, 120.0),
            id="connect-timeout-from-the-command-line",
        ),
    ],
)
def test_solr_timeouts_reach_the_solr_client(
    monkeypatch: pytest.MonkeyPatch, options: list[str], expected: tuple[float, float]
) -> None:
    arguments = _arguments(monkeypatch, *options)

    assert arguments.solr_api_full_text.timeout == expected


@pytest.mark.parametrize("option", ["--solr_timeout", "--solr_connect_timeout"])
def test_an_invalid_solr_timeout_exits_with_an_error(
    monkeypatch: pytest.MonkeyPatch, option: str
) -> None:
    """Which values are invalid is tested once, on positive_seconds (ht_indexer_api_test.py)."""
    with pytest.raises(SystemExit) as exit_info:
        _arguments(monkeypatch, option, "0")

    assert exit_info.value.code == 2
