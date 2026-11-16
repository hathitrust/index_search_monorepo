import sys
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from document_indexer_service import document_indexer_local_service
from ht_utils.testing import assert_log_entry, capture_logs


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


class _StopLoop(BaseException):
    """Raised from the patched sleep to leave the endless indexing loop (not caught by except Exception)."""


def _answer(status_code: int) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    return response


def _http_error(status_code: int) -> requests.exceptions.HTTPError:
    return requests.exceptions.HTTPError(f"{status_code} error", response=_answer(status_code))


def _run_one_pass(
    folder: Path, answers: Mapping[str, requests.Response | Exception]
) -> tuple[MagicMock, list[MutableMapping[str, Any]]]:
    """Run the indexing loop for one pass. `answers` says what Solr does for each file name.
    Returns the Solr client mock and the log entries."""

    def index_documents_by_file(path: str, list_documents: list[str]) -> requests.Response:
        answer = answers[list_documents[0]]
        if isinstance(answer, Exception):
            raise answer
        return answer

    solr_api = MagicMock()
    solr_api.index_documents_by_file.side_effect = index_documents_by_file
    service = document_indexer_local_service.DocumentIndexerLocalService(solr_api)
    with (
        capture_logs() as logs,
        patch.object(document_indexer_local_service, "sleep", side_effect=_StopLoop),
        pytest.raises(_StopLoop),
    ):
        service.indexer_service(str(folder))
    return solr_api, logs


def _make_files(folder: Path, *names: str) -> None:
    for name in names:
        (folder / name).write_text("{}")


def test_a_file_that_solr_rejects_is_logged_and_kept(tmp_path: Path) -> None:
    _make_files(tmp_path, "a.json")

    _, logs = _run_one_pass(tmp_path, {"a.json": _http_error(400)})

    assert_log_entry(logs, event="local_indexing_failed", file="a.json", status_code=400)
    assert (tmp_path / "a.json").exists()


def test_a_rejected_file_does_not_hold_back_the_other_files(tmp_path: Path) -> None:
    _make_files(tmp_path, "bad.json", "good1.json", "good2.json")

    solr_api, _ = _run_one_pass(
        tmp_path,
        {"bad.json": _http_error(400), "good1.json": _answer(200), "good2.json": _answer(200)},
    )

    assert solr_api.index_documents_by_file.call_count == 3
    assert sorted(path.name for path in tmp_path.iterdir()) == ["bad.json"]


def test_files_are_cleaned_up_after_any_successful_answer(tmp_path: Path) -> None:
    """Not only after a 200: Solr or a proxy can answer 204."""
    _make_files(tmp_path, "a.json")

    _run_one_pass(tmp_path, {"a.json": _answer(204)})

    assert list(tmp_path.iterdir()) == []


def test_the_pass_stops_when_solr_cannot_be_reached(tmp_path: Path) -> None:
    _make_files(tmp_path, "a.json", "b.json")

    solr_api, logs = _run_one_pass(
        tmp_path,
        {name: requests.exceptions.ConnectionError("down") for name in ("a.json", "b.json")},
    )

    # The second file would fail the same way, so it is not tried
    assert solr_api.index_documents_by_file.call_count == 1
    assert_log_entry(logs, event="local_indexing_failed", status_code=None)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["a.json", "b.json"]
