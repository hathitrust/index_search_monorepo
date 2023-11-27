import logging
from utils.ht_logger import HTLogger


def test_info_log_stdout():
    my_log = HTLogger("my_log", log_dir=None, set_level=logging.DEBUG)
    my_log.info("We now log stdout")
    assert 0 == 0


def test_error_log_stdout():
    my_log = HTLogger("my_error_log", log_dir=None, set_level=logging.ERROR)
    try:
        x = 1 / 0
    except ZeroDivisionError as e:
        my_log.error(f"Zero division Error {e}")
    assert 0 == 0


def test_error_log_file():
    my_log = HTLogger("my_error_log", log_dir="logs", set_level=logging.DEBUG)
    try:
        x = 1 / 0
    except ZeroDivisionError as e:
        my_log.error(f"Zero division Error {e}")
    assert 0 == 0
