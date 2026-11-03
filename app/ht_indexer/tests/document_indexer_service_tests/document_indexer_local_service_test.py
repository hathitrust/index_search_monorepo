import sys
from unittest.mock import MagicMock, patch

import pytest
from document_indexer_service import document_indexer_local_service


def _run_main(monkeypatch: pytest.MonkeyPatch, *extra: str) -> MagicMock:
    """Run main() with the indexing loop replaced; return the HTSolrAPI it built."""
    monkeypatch.setattr(
        sys, "argv", ["indexer", "--solr_indexing_api", "http://solr-lss-dev:8983/solr/", *extra]
    )
    with patch.object(document_indexer_local_service, "DocumentIndexerLocalService") as service:
        document_indexer_local_service.main()
    solr_api: MagicMock = service.call_args.args[0]
    return solr_api


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        pytest.param([], (10.0, 120.0), id="default"),
        pytest.param(
            ["--solr_timeout", "600"], (10.0, 600.0), id="read-timeout-from-the-command-line"
        ),
    ],
)
def test_solr_timeout_reaches_the_solr_client_of_the_local_indexer(
    monkeypatch: pytest.MonkeyPatch, options: list[str], expected: tuple[float, float]
) -> None:
    assert _run_main(monkeypatch, *options).timeout == expected


def test_the_local_indexer_exits_with_an_error_for_an_invalid_solr_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Which values are invalid is tested once, on positive_seconds (ht_indexer_api_test.py)."""
    with pytest.raises(SystemExit) as exit_info:
        _run_main(monkeypatch, "--solr_timeout", "0")

    assert exit_info.value.code == 2
