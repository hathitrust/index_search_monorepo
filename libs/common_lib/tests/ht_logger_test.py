import pytest
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class TestHTLogger:
    def test_info_log_stdout(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level("INFO", logger="my_log")
        my_log = get_ht_logger(name="my_log", log_level="INFO")
        my_log.info("We now log stdout")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert caplog.records[0].message == "We now log stdout"

    def test_error_log_file(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level("WARNING", logger="my_error_log_warning")
        my_log = get_ht_logger(name="my_error_log_debug", log_level="WARNING")
        try:
            print(1 / 0)
        except ZeroDivisionError as e:
            my_log.error(f"Zero division Error {e}")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"
        assert caplog.records[0].message == "Zero division Error division by zero"

    def test_error_log_stdout(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level("ERROR", logger="my_error_log")
        my_log = get_ht_logger(name="my_error_log")
        try:
            print(1 / 0)
        except ZeroDivisionError as e:
            my_log.error(f"Zero division Error {e}")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"
        assert caplog.records[0].message == "Zero division Error division by zero"
