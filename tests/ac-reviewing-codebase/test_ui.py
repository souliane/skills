"""Tests for the shared console module."""

from _cli_import import load

ui = load("ui")


class TestTruncate:
    def test_short_string_unchanged(self) -> None:
        assert ui.truncate("hello", 10) == "hello"

    def test_exact_length_unchanged(self) -> None:
        assert ui.truncate("12345", 5) == "12345"

    def test_long_string_truncated(self) -> None:
        result = ui.truncate("a very long string indeed", 10)
        assert len(result) == 10
        assert result.endswith("...")
