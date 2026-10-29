import argparse
import sys

import pytest
import yaml
from document_indexer_service import indexer_config_file_path
from document_indexer_service.indexer_arguments import IndexerServiceArguments

SOLR_URL = "http://solr-lss-dev:8983/solr/core-x/"


def _arguments(monkeypatch: pytest.MonkeyPatch, *extra: str) -> IndexerServiceArguments:
    """Parse a command line the way the indexer does, with the real indexer_config.yml."""
    monkeypatch.setenv("SOLR_USER", "solr_user")
    monkeypatch.setenv("SOLR_PASSWORD", "solr_password")
    monkeypatch.setattr(sys, "argv", ["indexer", "--solr_indexing_api", SOLR_URL, *extra])
    return IndexerServiceArguments(argparse.ArgumentParser())


def _configured_batch_size() -> int:
    config_file = indexer_config_file_path / "indexer_config.yml"
    batch_size: int = yaml.safe_load(config_file.read_text())["queue"]["batch_size"]
    return batch_size


def test_batch_size_on_the_command_line_overrides_indexer_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(monkeypatch, "--batch_size", "25")

    assert arguments.queue_config.queue_params.batch_size == 25
    assert arguments.queue_config.queue_params.batch_size != _configured_batch_size()


def test_without_batch_size_the_value_from_indexer_config_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(monkeypatch)

    assert arguments.queue_config.queue_params.batch_size == _configured_batch_size()


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


def test_solr_timeout_defaults_to_the_documented_values(monkeypatch: pytest.MonkeyPatch) -> None:
    arguments = _arguments(monkeypatch)

    assert arguments.solr_api_full_text.timeout == (10.0, 120.0)


def test_solr_timeout_on_the_command_line_sets_the_read_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(monkeypatch, "--solr_timeout", "30")

    assert arguments.solr_api_full_text.timeout == (10.0, 30.0)


@pytest.mark.parametrize("value", ["0", "-5", "soon"])
def test_solr_timeout_must_be_a_positive_number(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        _arguments(monkeypatch, "--solr_timeout", value)

    assert exit_info.value.code == 2
