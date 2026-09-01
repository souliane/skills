"""Tests for the suppression report.

The defect these guard: one headline number ("5330, noqa: 5091") read as a flat
contradiction of the repo's standard, when the truth was one deliberate pattern
in a vendored upstream and almost nothing first-party.
"""

from pathlib import Path

import pytest
from _cli_import import load

suppressions = load("suppressions")
vendored_paths = load("vendored_paths")

VENDOR = vendored_paths.VendoredPaths(("vendor",), "test")
NOTHING = vendored_paths.VendoredPaths()


def _write(root: Path, name: str, body: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


class TestScopeSplit:
    def test_vendored_suppressions_are_not_counted_against_the_repo(self, tmp_path: Path) -> None:
        _write(tmp_path, "src/app.py", "x = 1  # noqa: E501\n")
        _write(tmp_path, "vendor/dep.py", "a = 1  # noqa: PLC0415\nb = 2  # noqa: PLC0415\n")
        result = suppressions.count(tmp_path, VENDOR)
        assert result["total"] == 3
        assert result["scopes"]["first_party"]["total"] == 1
        assert result["scopes"]["vendored"]["total"] == 2

    def test_without_a_vendored_declaration_everything_is_first_party(self, tmp_path: Path) -> None:
        _write(tmp_path, "vendor/dep.py", "a = 1  # noqa: PLC0415\n")
        result = suppressions.count(tmp_path, NOTHING)
        assert result["scopes"]["first_party"]["total"] == 1
        assert result["scopes"]["vendored"]["total"] == 0


class TestRuleCodes:
    def test_one_dominant_rule_is_visible_next_to_the_total(self, tmp_path: Path) -> None:
        # A single intentional convention must not read as broad debt.
        body = "".join(f"x{i} = {i}  # noqa: PLC0415\n" for i in range(10))
        _write(tmp_path, "vendor/dep.py", body + "y = 1  # noqa: BLE001\n")
        codes = suppressions.count(tmp_path, VENDOR)["scopes"]["vendored"]["top_codes"]
        assert next(iter(codes.items())) == ("PLC0415", 10)
        assert codes["BLE001"] == 1

    def test_top_codes_are_capped(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", "".join(f"x{i} = {i}  # noqa: RUF{i:03d}\n" for i in range(10)))
        codes = suppressions.count(tmp_path, NOTHING)["scopes"]["first_party"]["top_codes"]
        assert len(codes) == suppressions.TOP_CODES

    @pytest.mark.parametrize(
        ("kind", "comment", "expected"),
        [
            ("noqa", "# noqa: E501", ["E501"]),
            ("noqa", "# noqa:E501,F401", ["E501", "F401"]),
            ("noqa", "# noqa: E501, F401  # explained", ["E501", "F401"]),
            ("noqa", "# noqa", []),
            ("noqa", "# noqa: because reasons", []),
            ("type_ignore", "# type: ignore[arg-type]", ["arg-type"]),
            ("type_ignore", "# type: ignore", []),
            ("pragma_no_cover", "# pragma: no cover", []),
        ],
    )
    def test_codes_are_read_off_the_comment(self, kind: str, comment: str, expected: list[str]) -> None:
        assert suppressions.codes_in(kind, comment) == expected


class TestUncoded:
    def test_a_bare_noqa_is_counted_apart_from_a_coded_one(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", "x = 1  # noqa\ny = 2  # noqa: E501\n")
        scope = suppressions.count(tmp_path, NOTHING)["scopes"]["first_party"]
        assert scope["total"] == 2
        assert scope["uncoded"] == 1
        assert scope["uncoded_by_kind"] == {"noqa": 1}

    def test_a_repo_with_only_coded_suppressions_reports_zero_uncoded(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", "x = 1  # noqa: E501\ny = 2  # type: ignore[arg-type]\n")
        assert suppressions.count(tmp_path, NOTHING)["uncoded"] == 0

    def test_pragma_no_cover_can_never_be_uncoded(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", "x = 1  # pragma: no cover\n")
        result = suppressions.count(tmp_path, NOTHING)
        assert result["total"] == 1
        assert result["uncoded"] == 0


class TestMentionsAreNotSuppressions:
    """A repo that reasons about suppressions writes the markers in prose.

    Counting docstrings and string literals inflated one fork's bare-``# noqa``
    figure from 2 to 49. Counting *comments about* the markers then left it
    reporting 2 where the truth is 0 — and that is the number printed in red,
    the one a reader would act on.
    """

    def test_a_docstring_mention_is_not_a_suppression(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", '"""Explains why a bare ``# noqa`` is bad form."""\nx = 1\n')
        assert suppressions.count(tmp_path, NOTHING)["total"] == 0

    def test_a_string_literal_mention_is_not_a_suppression(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", 'MESSAGE = "found  # noqa on an added line"\nPATTERNS = {"noqa": "# noqa"}\n')
        assert suppressions.count(tmp_path, NOTHING)["total"] == 0

    def test_a_comment_about_a_bare_noqa_is_not_a_bare_noqa(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", "# A `# noqa` with no codes is an unjustified blanket.\nx = 1\n")
        result = suppressions.count(tmp_path, NOTHING)
        assert result["total"] == 0
        assert result["uncoded"] == 0

    @pytest.mark.parametrize(
        "body",
        [
            "def f():\n    # noqa: E501\n    return 1\n",
            "def f():\n    # pragma: no cover\n    return 1\n",
            "def f():\n    # type: ignore[arg-type]\n    return 1\n",
        ],
    )
    def test_a_line_marker_that_trails_no_code_suppresses_nothing(self, tmp_path: Path, body: str) -> None:
        # ruff's own RUF100 calls such a marker unused; counting it invents debt.
        _write(tmp_path, "app.py", body)
        assert suppressions.count(tmp_path, NOTHING)["total"] == 0

    def test_the_real_suppression_beside_the_mentions_still_counts(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "app.py",
            '"""Mentions ``# noqa`` in prose."""\nMESSAGE = "a bare # noqa is bad"\nx = 1  # noqa: E501\n',
        )
        result = suppressions.count(tmp_path, NOTHING)
        assert result["total"] == 1
        assert result["scopes"]["first_party"]["top_codes"] == {"E501": 1}


class TestFileLevelDirectives:
    """``# ruff: noqa`` on its own line silences a whole file, not a line.

    Counted as one per-line suppression it understates itself by the size of
    the file; not counted at all — which is what a line-trailing-only scan
    does — the strongest suppression in the repo is invisible.
    """

    @pytest.mark.parametrize("marker", ["# ruff: noqa: SLF001", "# flake8: noqa: SLF001"])
    def test_a_file_level_directive_is_counted_and_labelled(self, tmp_path: Path, marker: str) -> None:
        _write(tmp_path, "app.py", f"{marker}\nx = 1\n")
        scope = suppressions.count(tmp_path, NOTHING)["scopes"]["first_party"]
        assert scope["by_kind"] == {suppressions.FILE_NOQA: 1}
        assert scope["file_level"] == 1
        assert scope["top_codes"] == {"SLF001": 1}

    def test_a_file_level_directive_with_no_codes_is_uncoded(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", "# ruff: noqa\nx = 1\n")
        result = suppressions.count(tmp_path, NOTHING)
        assert result["uncoded"] == 1
        assert result["file_level"] == 1

    def test_a_justification_after_the_codes_does_not_hide_them(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", "# ruff: noqa: SLF001 - sibling-module extraction (#1280).\nx = 1\n")
        assert suppressions.count(tmp_path, NOTHING)["uncoded"] == 0

    def test_a_line_directive_is_not_also_read_as_file_level(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", "x = 1  # noqa: E501\n")
        assert suppressions.count(tmp_path, NOTHING)["file_level"] == 0


class TestOneCommentTwoKinds:
    def test_each_suppression_on_a_line_is_its_own_decision(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", "x = 1  # noqa: E501  # type: ignore\n")
        scope = suppressions.count(tmp_path, NOTHING)["scopes"]["first_party"]
        assert scope["by_kind"] == {"noqa": 1, "type_ignore": 1}
        assert scope["uncoded_by_kind"] == {"type_ignore": 1}


class TestUnparsableFiles:
    def test_a_file_that_will_not_tokenize_is_reported_not_silently_dropped(self, tmp_path: Path) -> None:
        _write(tmp_path, "broken.py", "x = (  # noqa\n")
        result = suppressions.count(tmp_path, NOTHING)
        assert result["unparsed_files"] == 1
        assert result["total"] == 0

    def test_a_clean_repo_reports_no_unparsed_files(self, tmp_path: Path) -> None:
        _write(tmp_path, "app.py", "x = 1  # noqa: E501\n")
        assert suppressions.count(tmp_path, NOTHING)["unparsed_files"] == 0
