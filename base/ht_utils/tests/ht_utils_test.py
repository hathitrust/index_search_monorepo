import arrow
from ht_utils import get_current_time


class TestHTTime:

    def test_current_time(self):
        assert arrow.now().format("YYYY-MM-DD HH:mm:ss") == get_current_time(arrow.now(), "YYYY-MM-DD HH:mm:ss")
