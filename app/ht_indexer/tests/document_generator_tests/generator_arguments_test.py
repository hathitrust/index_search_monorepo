import argparse
import sys

import pytest
from document_generator.generator_arguments import GeneratorServiceArguments

SOLR_URL = "http://solr-lss-dev:8983/solr/core-x/"


def _arguments(monkeypatch: pytest.MonkeyPatch, *extra: str) -> GeneratorServiceArguments:
    """Parse a command line the way the generator does, with the real generator_config.yml."""
    monkeypatch.setattr(sys, "argv", ["generator", *extra])
    return GeneratorServiceArguments(argparse.ArgumentParser())


def test_accepts_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(
        monkeypatch,
        "--document_repository",
        "pairtree",
        "--document_local_path",
        "/path/to/documents",
        "--tgt_local",
    )

    assert arguments.document_repository == "pairtree"
    assert arguments.document_local_path == "/path/to/documents"
    assert arguments.tgt_local


def test_default_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(monkeypatch)

    assert arguments.document_repository == "local"
    assert arguments.document_local_path is None
    assert not arguments.tgt_local
