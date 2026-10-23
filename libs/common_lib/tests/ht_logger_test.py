from ht_utils.ht_logger import get_ht_logger
from ht_utils.testing import assert_log_entry, capture_logs

logger = get_ht_logger(name=__name__)


class TestHTLogger:
    def test_info_log(self) -> None:
        with capture_logs() as entries:
            my_log = get_ht_logger(name="my_log")
            my_log.info("We now log stdout")

            assert len(entries) == 1
            assert_log_entry(entries, log_level="info", event="We now log stdout")

    def test_error_log(self) -> None:
        with capture_logs() as entries:
            my_log = get_ht_logger(name="my_error_log")
            try:
                print(1 / 0)
            except ZeroDivisionError as e:
                my_log.error(f"Zero division Error {e}")

            assert len(entries) == 1
            assert_log_entry(
                entries, log_level="error", event="Zero division Error division by zero"
            )
