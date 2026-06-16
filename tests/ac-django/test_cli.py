"""End-to-end CLI meta-tests via typer's CliRunner."""

from pathlib import Path

from _loader import cli
from typer.testing import CliRunner

runner = CliRunner()

BAD_DJANGO_DB = "import pytest\n\n\n@pytest.mark.django_db\ndef test_thing():\n    assert True\n"
GOOD_TESTCASE = "from django.test import TestCase\n\n\nclass T(TestCase):\n    def test_x(self):\n        pass\n"


def _write(tmp_path: Path, name: str, content: str) -> str:
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target)


class TestNoArgStrict:
    def test_strict_default_fails_on_violation(self, tmp_path: Path) -> None:
        bad = _write(tmp_path, "test_bad.py", BAD_DJANGO_DB)
        result = runner.invoke(cli.app, ["no-django-db", bad])
        assert result.exit_code == 1
        assert "django_db" in result.output

    def test_strict_default_passes_clean_file(self, tmp_path: Path) -> None:
        good = _write(tmp_path, "test_good.py", GOOD_TESTCASE)
        result = runner.invoke(cli.app, ["no-django-db", good])
        assert result.exit_code == 0


class TestAllowArg:
    def test_inline_allow_grandfathers(self, tmp_path: Path) -> None:
        bad = _write(tmp_path, "test_bad.py", BAD_DJANGO_DB)
        result = runner.invoke(cli.app, ["no-django-db", bad, f"--allow={bad}"])
        assert result.exit_code == 0


class TestBaselineRoundtrip:
    def test_update_then_pass(self, tmp_path: Path) -> None:
        bad = _write(tmp_path, "test_bad.py", BAD_DJANGO_DB)
        baseline = tmp_path / "db.baseline"
        update = runner.invoke(
            cli.app,
            ["no-django-db", bad, f"--baseline={baseline}", "--update-baseline"],
        )
        assert update.exit_code == 0
        assert baseline.exists()
        rerun = runner.invoke(cli.app, ["no-django-db", bad, f"--baseline={baseline}"])
        assert rerun.exit_code == 0

    def test_partial_update_preserves_unscanned_entries(self, tmp_path: Path) -> None:
        # Updating over only one file must not drop a baseline entry for a file
        # that was not part of this invocation.
        bad = _write(tmp_path, "test_bad.py", BAD_DJANGO_DB)
        baseline = tmp_path / "db.baseline"
        baseline.write_text("tests/legacy/test_old.py\n", encoding="utf-8")
        result = runner.invoke(
            cli.app,
            ["no-django-db", bad, f"--baseline={baseline}", "--update-baseline"],
        )
        assert result.exit_code == 0
        contents = baseline.read_text(encoding="utf-8").splitlines()
        assert "tests/legacy/test_old.py" in contents

    def test_new_violation_after_baseline_fails(self, tmp_path: Path) -> None:
        bad = _write(tmp_path, "test_bad.py", BAD_DJANGO_DB)
        baseline = tmp_path / "db.baseline"
        runner.invoke(cli.app, ["no-django-db", bad, f"--baseline={baseline}", "--update-baseline"])
        new_bad = _write(tmp_path, "test_new.py", BAD_DJANGO_DB)
        result = runner.invoke(cli.app, ["no-django-db", bad, new_bad, f"--baseline={baseline}"])
        assert result.exit_code == 1
        assert "test_new.py" in result.output


class TestComplexityPyproject:
    def test_flags_pyproject_complexity_ignore(self, tmp_path: Path) -> None:
        pyproject = _write(
            tmp_path,
            "pyproject.toml",
            '[tool.ruff]\nlint.ignore = ["C901"]\n',
        )
        result = runner.invoke(cli.app, ["no-complexity-suppressions", pyproject])
        assert result.exit_code == 1
        assert "C901" in result.output
