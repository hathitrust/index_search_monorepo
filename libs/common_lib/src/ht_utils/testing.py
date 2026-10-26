from collections.abc import Generator, MutableMapping
from contextlib import contextmanager
from typing import Any

import structlog


@contextmanager
def capture_logs() -> Generator[list[structlog.typing.EventDict]]:
    with structlog.testing.capture_logs(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.dict_tracebacks,
        ]
    ) as caplog:
        yield caplog


def assert_log_entry(entries: list[MutableMapping[str, Any]], **kwargs: Any) -> None:
    """Asserts that the fields in the keyword arguments are included in at least one of
    the log entries in entries."""

    assert find_log_entry(entries, **kwargs) is not None


def find_log_entry(
    entries: list[MutableMapping[str, Any]], **kwargs: Any
) -> MutableMapping[str, Any]:
    """Returns the first log entry matching the fields from the given keyword arguments"""
    return next(e for e in entries if kwargs.items() <= e.items())
