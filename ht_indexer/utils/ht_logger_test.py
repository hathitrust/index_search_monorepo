from utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class TestHTLogger():
    def test_info_log_stdout(self, caplog):
        caplog.set_level("INFO", logger="my_log")
        my_log = get_ht_logger(name="my_log", log_level="INFO")
        my_log.info("We now log stdout")
        assert 0 == 0

    def test_error_log_file(self, caplog):
        caplog.set_level("WARNING", logger="my_error_log_warning")
        my_log = get_ht_logger(name="my_error_log_debug", log_level="WARNING")
        try:
            x = 1 / 0
        except ZeroDivisionError as e:
            my_log.error(f"Zero division Error {e}")
        assert 0 == 0

    def test_error_log_stdout(self, caplog):
        caplog.set_level("ERROR", logger="my_error_log")
        my_log = get_ht_logger(name="my_error_log")
        try:
            x = 1 / 0
        except ZeroDivisionError as e:
            my_log.error(f"Zero division Error {e}")
        assert 0 == 0
