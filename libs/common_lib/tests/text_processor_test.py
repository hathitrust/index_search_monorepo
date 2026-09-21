import pytest
from ht_utils.text_processor import ensure_text, first_value, list_values, string_preparation

# --- string_preparation ---------------------------------------------------


def test_string_preparation_strips_and_quotes() -> None:
    assert string_preparation(b"  Hello World  ") == '"Hello World"'


def test_string_preparation_collapses_line_breaks_to_spaces() -> None:
    assert string_preparation(b"Hello\r\nWorld\ragain") == '"Hello  World again"'


def test_string_preparation_invalid_utf8_raises() -> None:
    with pytest.raises(UnicodeDecodeError):
        string_preparation(b"\xff\xfe")


# --- ensure_text ------------------------------------------------------------


def test_ensure_text_none_returns_empty_string() -> None:
    assert ensure_text(None) == ""


def test_ensure_text_strips_a_string() -> None:
    assert ensure_text("  hi  ") == "hi"


def test_ensure_text_stringifies_non_string_values() -> None:
    assert ensure_text(5) == "5"
    assert ensure_text(3.5) == "3.5"


# --- first_value --------------------------------------------------------


def test_first_value_returns_first_non_empty_item_in_list() -> None:
    assert first_value(["", "  ", "value", "other"]) == "value"


def test_first_value_works_on_tuples() -> None:
    assert first_value(("", "value")) == "value"


def test_first_value_returns_empty_string_when_all_items_blank() -> None:
    assert first_value(["", "   ", None]) == ""


def test_first_value_returns_empty_string_for_empty_list() -> None:
    assert first_value([]) == ""


def test_first_value_delegates_to_ensure_text_for_non_list_input() -> None:
    assert first_value("  hi  ") == "hi"
    assert first_value(None) == ""


# --- list_values --------------------------------------------------------


def test_list_values_none_returns_empty_list() -> None:
    assert list_values(None) == []


def test_list_values_filters_out_blank_items() -> None:
    assert list_values(["a", "", "  ", "b"]) == ["a", "b"]


def test_list_values_works_on_tuples() -> None:
    assert list_values(("a", "b")) == ["a", "b"]


def test_list_values_wraps_a_single_non_list_value() -> None:
    assert list_values("  hi  ") == ["hi"]


def test_list_values_single_blank_value_returns_empty_list() -> None:
    assert list_values("   ") == []
