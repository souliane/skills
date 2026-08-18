"""Tests for what the ``assess`` report actually tells the reader.

Each of these guards a sentence a reader would otherwise have to guess at: what
a count covers, where the vendored split came from, and when a number is
missing rather than zero.
"""

import re

import pytest
from _cli_import import load

metrics_report = load("metrics_report")
ui = load("ui")


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _render(metrics: dict) -> str:
    with ui.console.capture() as captured:
        metrics_report.print_report(metrics)
    return _ANSI_RE.sub("", captured.get())


def _payload(**overrides: dict) -> dict:
    base = {
        "vendored": {"paths": ["vendor"], "source": "pyproject [tool.ruff] exclude"},
        "lint": {"total": 0, "by_category": {}},
        "todos": {"total": 3, "by_type": {"TODO": 3}, "scopes": {"first_party": 1, "vendored": 2}},
        "complexity": {"violations": 0},
        "coverage": {
            "available": True,
            "percent": 70.0,
            "scopes": {
                "first_party": {"files": 56, "measured": 1000, "percent": 70.0},
                "vendored": {"files": 0, "measured": 0, "percent": None},
            },
        },
        "dependencies": {"available": False},
        "suppressions": {
            "total": 11,
            "uncoded": 0,
            "file_level": 0,
            "unparsed_files": 0,
            "scopes": {
                "first_party": {
                    "total": 1,
                    "by_kind": {"noqa": 1},
                    "uncoded": 0,
                    "uncoded_by_kind": {},
                    "file_level": 0,
                    "top_codes": {"E501": 1},
                },
                "vendored": {
                    "total": 10,
                    "by_kind": {"noqa": 10},
                    "uncoded": 0,
                    "uncoded_by_kind": {},
                    "file_level": 0,
                    "top_codes": {"PLC0415": 10},
                },
            },
        },
    }
    return base | overrides


class TestVendoredBanner:
    def test_the_report_names_the_vendored_paths_and_where_they_came_from(self) -> None:
        output = _render(_payload())
        assert "vendor" in output
        assert "tool.ruff" in output

    def test_a_repo_with_no_vendored_declaration_says_the_counts_are_whole_repo(self) -> None:
        output = _render(_payload(vendored={"paths": [], "source": "nothing declared"}))
        assert "whole repo" in output

    def test_an_undeclared_repo_shows_no_empty_vendored_rows(self) -> None:
        output = _render(_payload(vendored={"paths": [], "source": "nothing declared"}))
        assert "vendored" not in output


class TestSuppressionReporting:
    def test_the_dominant_rule_code_is_printed_beside_the_total(self) -> None:
        # Without this the reader sees "11 suppressions" and infers broad debt.
        output = _render(_payload())
        assert "PLC0415" in output

    def test_first_party_and_vendored_totals_are_both_shown(self) -> None:
        output = _render(_payload())
        assert "first-party 1" in output
        assert "vendored 10" in output

    def test_uncoded_suppressions_get_their_own_line(self) -> None:
        assert "uncoded" in _render(_payload())

    def test_files_that_would_not_tokenize_are_surfaced(self) -> None:
        payload = _payload()
        payload["suppressions"]["unparsed_files"] = 2
        assert "NOT counted" in _render(payload)

    def test_a_file_level_directive_says_it_covers_a_whole_file(self) -> None:
        # Folded into the per-line total it reads as one suppression, not one file.
        payload = _payload()
        payload["suppressions"]["scopes"]["vendored"]["file_level"] = 2
        assert "whole file" in _render(payload)

    def test_no_file_level_directive_adds_no_line(self) -> None:
        assert "whole file" not in _render(_payload())


class TestCoverageReporting:
    def test_the_percentage_says_which_files_it_covers(self) -> None:
        output = _render(_payload())
        assert "56 files" in output

    def test_an_unmeasured_scope_reads_as_not_measured_not_zero(self) -> None:
        output = _render(_payload())
        assert "not measured" in output

    @pytest.mark.parametrize(
        ("coverage", "expected"),
        [
            ({"available": False}, "no .coverage file"),
            ({"available": False, "error": "coverage json failed: No source for code"}, "No source for code"),
        ],
    )
    def test_unavailable_coverage_says_why(self, coverage: dict, expected: str) -> None:
        assert expected in _render(_payload(coverage=coverage))


class TestTodoReporting:
    def test_todos_are_split_when_a_vendored_tree_is_declared(self) -> None:
        output = _render(_payload())
        assert "first-party 1" in output
        assert "vendored 2" in output
