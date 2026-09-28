"""CLI script that prints a grouped-count status report for a list of ht_ids.

Re-runnable during a pipeline run: reads ht_ids from a file and prints a table
grouped by (retriever_status, generator_status, indexer_status, status).
"""

import argparse
from collections import defaultdict
from pathlib import Path

from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_mysql import HtMysql, get_mysql_conn

from ht_indexer_monitoring.ht_indexer_tracktable import PROCESSING_STATUS_TABLE_NAME

logger = get_ht_logger(name=__name__)

_STATUS_COLUMNS: tuple[str, str, str, str] = (
    "retriever_status",
    "generator_status",
    "indexer_status",
    "status",
)


def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def build_status_counts(
    db_conn: HtMysql,
    ht_ids: list[str],
    chunk_size: int = 500,
) -> dict[tuple[str, str, str, str], int]:
    """Query MySQL and return counts grouped by
    (retriever_status, generator_status, indexer_status, status).

    Chunks ht_ids into batches of at most chunk_size to avoid oversized IN clauses.
    Returns an empty dict if ht_ids is empty.
    """
    counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    if not ht_ids:
        return dict(counts)

    for chunk in _chunk(ht_ids, chunk_size):
        # Build parameterized IN clause: named placeholders are the safest cross-driver
        # approach with HtMysql.query_mysql (SQLAlchemy text() + params dict).
        placeholders = ", ".join(f":id_{i}" for i in range(len(chunk)))
        query = (
            f"SELECT retriever_status, generator_status, indexer_status, status, "
            f"COUNT(*) AS cnt "
            f"FROM {PROCESSING_STATUS_TABLE_NAME} "
            f"WHERE ht_id IN ({placeholders}) "
            f"GROUP BY retriever_status, generator_status, indexer_status, status"
        )
        params: dict[str, str] = {f"id_{i}": ht_id for i, ht_id in enumerate(chunk)}
        rows = db_conn.query_mysql(query, params)
        for row in rows:
            key = (
                str(row["retriever_status"]),
                str(row["generator_status"]),
                str(row["indexer_status"]),
                str(row["status"]),
            )
            counts[key] += int(row["cnt"])

    return dict(counts)


def print_status_report(
    db_conn: HtMysql,
    ht_ids: list[str],
    chunk_size: int = 500,
) -> None:
    """Print a grouped count table to stdout, followed by a Total footer."""
    counts = build_status_counts(db_conn, ht_ids, chunk_size)
    total = sum(counts.values())

    headers = list(_STATUS_COLUMNS) + ["count"]
    rows: list[list[str]] = [
        [rs, gs, ixs, s, str(c)] for (rs, gs, ixs, s), c in sorted(counts.items())
    ]

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if len(cell) > widths[i]:
                widths[i] = len(cell)

    def _fmt(row_values: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row_values))

    print(_fmt(headers))
    print(_fmt(["-" * w for w in widths]))
    for row in rows:
        print(_fmt(row))
    print(f"Total: {total} items")


def _read_ht_ids(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print pipeline status report for a list of ht_ids."
    )
    parser.add_argument(
        "--ht_id_file",
        required=True,
        help="Path to file with one ht_id per line.",
    )
    parser.add_argument(
        "--chunk_size",
        type=int,
        default=500,
        help="Max ht_ids per SQL IN clause.",
    )
    args = parser.parse_args()

    ht_ids = _read_ht_ids(Path(args.ht_id_file))
    db_conn = get_mysql_conn(pool_size=1)
    print_status_report(db_conn, ht_ids, chunk_size=args.chunk_size)


if __name__ == "__main__":
    main()
