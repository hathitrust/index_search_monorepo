import csv
from collections.abc import Sequence
from pathlib import Path

import kbart_file_generator.kbart_file_generator as kbart_module
import pytest
from kbart_file_generator.kbart_file_generator import (
    KBART_COLUMN_ORDER,
    build_kbart_row,
    fetch_title_dates_from_mysql_batch,
    generate_kbart_rows,
    read_catalog_ids,
)


def write_holdings_report(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_read_catalog_ids_deduplicates_and_preserves_order(tmp_path: Path) -> None:
    report_path = write_holdings_report(
        tmp_path / "holdings.tsv",
        rows=[
            {"catalog_id": "0009040", "volume_id": "a"},
            {"catalog_id": "0009040", "volume_id": "b"},
            {"catalog_id": " 127531 ", "volume_id": "c"},
            {"catalog_id": "", "volume_id": "d"},
            {"catalog_id": "140237", "volume_id": "e"},
        ],
        fieldnames=["catalog_id", "volume_id"],
    )

    assert read_catalog_ids(report_path) == ["0009040", "127531", "140237"]


def test_build_kbart_row_maps_solr_fields_to_expected_columns() -> None:
    row = build_kbart_row(
        {
            "id": "0009040",
            "title_display": "Gerodontology",
            "isbn": ["07340664", "11111111"],
            "mainauthor": "Beech Hill Enterprises",
            "publisher": ["Beech Hill Enterprises,"],
            "oclc": ["8731707", "9999999"],
            "display_date": "1990",
        },
        {
            "date_first_issue_online": "2001",
            "date_last_issue_online": "2005",
            "bib_fmt": "SE",
        },
    )

    assert list(row) == KBART_COLUMN_ORDER
    assert row == {
        "publication_title": "Gerodontology",
        "print_identifier": "07340664",
        "online_identifier": "",
        "date_first_issue_online": "2001",
        "num_first_vol_online": "",
        "num_first_issue_online": "",
        "date_last_issue_online": "2005",
        "num_last_vol_online": "",
        "num_last_issue_online": "",
        "title_url": "https://catalog.hathitrust.org/Record/9040",
        "first author": "Beech Hill Enterprises",
        "title_id": "9040",
        "embargo_info": "",
        "coverage_depth": "",
        "coverage_notes": "",
        "publisher_name": "Beech Hill Enterprises,",
        "oclc_number": "8731707",
    }


def test_fetch_title_dates_from_mysql_batch_queries_one_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_queries: list[tuple[str, dict[str, str]]] = []

    class FakeMysqlConnection:
        def query_mysql(
            self, query: str, params: dict[str, str] | None = None
        ) -> list[dict[str, object]]:
            captured_queries.append((query, params or {}))
            if params == {"bib_num_0": "101703357", "bib_num_1": "000127531"}:
                return [
                    {
                        "bib_num": "101703357",
                        "date_first_issue_online": "2001",
                        "date_last_issue_online": "2005",
                    }
                ]
            return [
                {
                    "bib_num": "000140237",
                    "date_first_issue_online": "1998",
                    "date_last_issue_online": "1999",
                }
            ]

    fake_conn = FakeMysqlConnection()

    results = fetch_title_dates_from_mysql_batch(["101703357", "000127531"], fake_conn)

    assert len(captured_queries) == 1
    assert "MIN(rights_date_used) AS date_first_issue_online" in captured_queries[0][0]
    assert "MAX(rights_date_used) AS date_last_issue_online" in captured_queries[0][0]
    assert results == {
        "101703357": {
            "bib_num": "101703357",
            "date_first_issue_online": "2001",
            "date_last_issue_online": "2005",
        },
    }


def test_generate_kbart_rows_matches_zero_padded_ids_to_stripped_lookup_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lookup results are keyed by catalog id with leading zeros stripped; catalog_ids from
    the input file are zero-padded."""

    def fake_fetch_lookup_results_in_parallel(
        catalog_ids: Sequence[str], batch_size: int = 100
    ) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
        return (
            {
                "9040": {
                    "id": "0009040",
                    "title_display": "Gerodontology",
                    "isbn": ["07340664"],
                    "mainauthor": "Beech Hill Enterprises",
                    "publisher": ["Beech Hill Enterprises,"],
                    "oclc": ["8731707"],
                },
            },
            {
                "9040": {
                    "date_first_issue_online": "2001",
                    "date_last_issue_online": "2005",
                    "bib_fmt": "SE",
                },
            },
        )

    monkeypatch.setattr(
        kbart_module, "fetch_lookup_results_in_parallel", fake_fetch_lookup_results_in_parallel
    )

    rows, errors = generate_kbart_rows(["0009040"])

    assert errors == []
    assert len(rows) == 1
    assert rows[0]["title_id"] == "9040"
    assert rows[0]["publication_title"] == "Gerodontology"
    assert rows[0]["date_first_issue_online"] == "2001"
