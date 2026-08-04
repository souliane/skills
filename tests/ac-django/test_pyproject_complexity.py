"""Behaviour tests for the standalone pyproject complexity-suppression hook.

`test_astgrep_rules.py` drives this hook as a subprocess, which proves it runs
standalone but leaves its hand-rolled TOML scanner unmeasured. The scanner is
where the hook can go wrong quietly: it decides which tables count as ruff
ignore lists, which codes are complexity codes, and where a multi-line array
ends. These call `main()` in-process and assert the reported `<code>@<location>`
key, so a scanner that flags the wrong thing — or the right thing under the
wrong location, which silently invalidates every `--grandfather` entry a
consuming repo has pinned — fails here.
"""

from pathlib import Path

import pyproject_complexity

HOOK_PREFIX = "ac-django-no-complexity-suppressions: "


def _write(tmp_path: Path, body: str, name: str = "pyproject.toml") -> str:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


class TestWhichTablesCountAsIgnoreLists:
    def test_a_complexity_code_outside_the_ruff_tables_is_not_a_suppression(self, tmp_path: Path) -> None:
        path = _write(tmp_path, '[tool.mypy]\ndisable_error_code = ["C901"]\n')
        assert pyproject_complexity.main([path]) == 0

    def test_select_enables_a_rule_rather_than_suppressing_it(self, tmp_path: Path) -> None:
        path = _write(tmp_path, '[tool.ruff.lint]\nselect = ["C901"]\n')
        assert pyproject_complexity.main([path]) == 0

    def test_extend_ignore_counts_alongside_ignore(self, tmp_path: Path, capsys) -> None:
        path = _write(tmp_path, '[tool.ruff.lint]\nextend-ignore = ["PLR0912"]\n')
        assert pyproject_complexity.main([path]) == 1
        assert "PLR0912@lint.extend-ignore" in capsys.readouterr().err

    def test_a_legacy_top_level_ignore_is_reported_under_the_lint_namespace(self, tmp_path: Path, capsys) -> None:
        path = _write(tmp_path, '[tool.ruff]\nignore = ["C901"]\n')
        assert pyproject_complexity.main([path]) == 1
        assert "C901@lint.ignore" in capsys.readouterr().err

    def test_a_dotted_key_already_carrying_the_lint_prefix_is_not_prefixed_twice(self, tmp_path: Path, capsys) -> None:
        path = _write(tmp_path, '[tool.ruff]\nlint.ignore = ["C901"]\n')
        assert pyproject_complexity.main([path]) == 1
        assert f"{HOOK_PREFIX}{path}: new complexity suppression C901@lint.ignore\n" == capsys.readouterr().err

    def test_the_legacy_per_file_ignores_table_reports_the_lint_namespaced_location(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        path = _write(tmp_path, '[tool.ruff.per-file-ignores]\n"tests/*.py" = ["C901"]\n')
        assert pyproject_complexity.main([path]) == 1
        assert "C901@lint.per-file-ignores.tests/*.py" in capsys.readouterr().err

    def test_a_code_named_only_in_a_comment_is_not_a_suppression(self, tmp_path: Path) -> None:
        body = '[tool.ruff.lint]\n# C901 was suppressed here once; it is not any more.\nignore = ["D100"]\n'
        assert pyproject_complexity.main([_write(tmp_path, body)]) == 0

    def test_a_table_header_with_a_trailing_comment_is_still_recognised(self, tmp_path: Path) -> None:
        path = _write(tmp_path, '[tool.ruff.lint]  # complexity rules stay on\nignore = ["C901"]\n')
        assert pyproject_complexity.main([path]) == 1


class TestWhichCodesCountAsComplexity:
    def test_the_plr09_family_is_flagged(self, tmp_path: Path) -> None:
        path = _write(tmp_path, '[tool.ruff.lint]\nignore = ["PLR0915"]\n')
        assert pyproject_complexity.main([path]) == 1

    def test_a_plr_code_outside_the_09_range_is_left_alone(self, tmp_path: Path) -> None:
        path = _write(tmp_path, '[tool.ruff.lint]\nignore = ["PLR1702", "PLR2004"]\n')
        assert pyproject_complexity.main([path]) == 0

    def test_an_unrelated_pl_code_is_left_alone(self, tmp_path: Path) -> None:
        path = _write(tmp_path, '[tool.ruff.lint]\nignore = ["PLC0415", "D100"]\n')
        assert pyproject_complexity.main([path]) == 0

    def test_a_longer_code_that_merely_starts_with_a_complexity_code_is_left_alone(self, tmp_path: Path) -> None:
        path = _write(tmp_path, '[tool.ruff.lint]\nignore = ["C9012"]\n')
        assert pyproject_complexity.main([path]) == 0


class TestMultiLineArrays:
    def test_a_code_on_a_later_line_of_an_array_is_found(self, tmp_path: Path, capsys) -> None:
        path = _write(tmp_path, '[tool.ruff.lint]\nignore = [\n  "D100",\n  "PLR0915",\n]\n')
        assert pyproject_complexity.main([path]) == 1
        assert "PLR0915@lint.ignore" in capsys.readouterr().err

    def test_an_array_stops_at_its_closing_bracket(self, tmp_path: Path) -> None:
        """A code on the key AFTER a multi-line array must not be swallowed into it."""
        body = '[tool.ruff.lint]\nignore = [\n  "D100",\n]\nselect = ["C901"]\n'
        assert pyproject_complexity.main([_write(tmp_path, body)]) == 0

    def test_a_quoted_per_file_key_keeps_its_glob_in_the_location(self, tmp_path: Path, capsys) -> None:
        body = '[tool.ruff.lint]\nper-file-ignores."scripts/**/*.py" = [\n  "D100",\n  "C901",\n]\n'
        assert pyproject_complexity.main([_write(tmp_path, body)]) == 1
        assert "C901@lint.per-file-ignores.scripts/**/*.py" in capsys.readouterr().err

    def test_an_unterminated_array_is_reported_rather_than_read_past_the_end(self, tmp_path: Path) -> None:
        assert pyproject_complexity.main([_write(tmp_path, '[tool.ruff.lint]\nignore = [\n  "C901",\n')]) == 1


class TestGrandfathering:
    def test_a_grandfathered_entry_passes(self, tmp_path: Path) -> None:
        path = _write(tmp_path, '[tool.ruff.lint]\nignore = ["C901"]\n')
        assert pyproject_complexity.main(["--grandfather", "C901@lint.ignore", path]) == 0

    def test_the_equals_form_is_accepted(self, tmp_path: Path) -> None:
        path = _write(tmp_path, '[tool.ruff.lint]\nignore = ["C901"]\n')
        assert pyproject_complexity.main(["--grandfather=C901@lint.ignore", path]) == 0

    def test_grandfathering_is_per_location(self, tmp_path: Path, capsys) -> None:
        body = '[tool.ruff.lint]\nignore = ["C901"]\nper-file-ignores."a.py" = ["C901"]\n'
        path = _write(tmp_path, body)
        assert pyproject_complexity.main(["--grandfather", "C901@lint.ignore", path]) == 1
        assert "lint.per-file-ignores" in capsys.readouterr().err

    def test_a_dangling_flag_does_not_grandfather_everything(self, tmp_path: Path) -> None:
        path = _write(tmp_path, '[tool.ruff.lint]\nignore = ["C901"]\n')
        assert pyproject_complexity.main([path, "--grandfather"]) == 1


class TestReporting:
    def test_a_clean_pyproject_is_silent(self, tmp_path: Path, capsys) -> None:
        path = _write(tmp_path, '[tool.ruff.lint]\nignore = ["D100", "COM812"]\n')
        assert pyproject_complexity.main([path]) == 0
        assert capsys.readouterr().err == ""

    def test_no_files_is_a_pass(self) -> None:
        assert pyproject_complexity.main([]) == 0

    def test_every_offending_file_is_named_in_its_own_line(self, tmp_path: Path, capsys) -> None:
        first = _write(tmp_path, '[tool.ruff.lint]\nignore = ["C901"]\n', "a.toml")
        second = _write(tmp_path, '[tool.ruff.lint]\nignore = ["PLR0912"]\n', "b.toml")
        assert pyproject_complexity.main([first, second]) == 1
        lines = capsys.readouterr().err.splitlines()
        assert [line.removeprefix(HOOK_PREFIX) for line in lines] == [
            f"{first}: new complexity suppression C901@lint.ignore",
            f"{second}: new complexity suppression PLR0912@lint.ignore",
        ]
