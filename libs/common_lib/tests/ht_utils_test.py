import arrow
import pytest

from ht_utils.ht_utils import get_current_time, normalize_catalog_id_pad_zeros


def test_normalize_id():

    assert "000000123" == normalize_catalog_id_pad_zeros("123")
    assert "123456789" == normalize_catalog_id_pad_zeros("123456789")


def test_normalize_id_raises_for_non_numeric():
    with pytest.raises(ValueError, match="ID cannot be empty"):
        normalize_catalog_id_pad_zeros(" ")

def test_current_time():
    assert arrow.now().format("YYYY-MM-DD HH:mm:ss") == get_current_time(arrow.now(), "YYYY-MM-DD HH:mm:ss")
