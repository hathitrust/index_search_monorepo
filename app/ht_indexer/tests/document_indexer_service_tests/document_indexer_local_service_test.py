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


def test_the_local_indexer_uses_the_default_solr_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run_main(monkeypatch).timeout == (10.0, 120.0)


def test_solr_timeout_sets_the_read_timeout_of_the_local_indexer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _run_main(monkeypatch, "--solr_timeout", "600").timeout == (10.0, 600.0)


@pytest.mark.parametrize("value", ["0", "-1", "inf", "soon"])
def test_the_local_indexer_rejects_an_invalid_solr_timeout(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        _run_main(monkeypatch, "--solr_timeout", value)

    assert exit_info.value.code == 2
