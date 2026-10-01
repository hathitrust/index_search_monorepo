import logging

import pytest
import structlog
from ht_utils.ht_logger import get_ht_logger
from structlog.testing import LogCapture


@pytest.fixture
def caplog() -> LogCapture:
    return LogCapture()


@pytest.fixture(autouse=True)
def fixture_configure_structlog(caplog: LogCapture) -> None:
    structlog.configure(processors=[caplog])


logger = get_ht_logger(name=__name__)


class TestHTLogger:
    def test_info_log_stdout(self, caplog: LogCapture) -> None:
        my_log = get_ht_logger(name="my_log", log_level=logging.INFO)
        my_log.info("We now log stdout")

        assert len(caplog.entries) == 1
        assert caplog.entries[0]["log_level"] == "info"
        assert caplog.entries[0]["event"] == "We now log stdout"

    def test_error_log_file(self, caplog: LogCapture) -> None:
        my_log = get_ht_logger(name="my_error_log_debug", log_level=logging.WARNING)
        try:
            print(1 / 0)
        except ZeroDivisionError as e:
            my_log.error(f"Zero division Error {e}")

        assert len(caplog.entries) == 1
        assert caplog.entries[0]["log_level"] == "error"
        assert caplog.entries[0]["event"] == "Zero division Error division by zero"

    def test_error_log_stdout(self, caplog: LogCapture) -> None:
        my_log = get_ht_logger(name="my_error_log")
        try:
            print(1 / 0)
        except ZeroDivisionError as e:
            my_log.error(f"Zero division Error {e}")

        assert len(caplog.entries) == 1
        assert caplog.entries[0]["log_level"] == "error"
        assert caplog.entries[0]["event"] == "Zero division Error division by zero"
