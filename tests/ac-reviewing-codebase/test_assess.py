"""Tests for the assess command in ac-reviewing-codebase CLI."""

import importlib.util
import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

CLI_PATH = Path(__file__).resolve().parents[2] / "ac-reviewing-codebase" / "scripts" / "cli.py"
SPEC = importlib.util.spec_from_file_location("reviewing_codebase_cli", CLI_PATH)
assert SPEC is not None
assert SPEC.loader is not None
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)

runner = CliRunner()


class TestCountTodos:
    def test_empty_dir(self, tmp_path: Path) -> None:
        result = cli._count_todos(tmp_path)
        assert result["total"] == 0

    def test_finds_todos(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("# TODO: fix this\n# FIXME: broken\n", encoding="utf-8")
        result = cli._count_todos(tmp_path)
        assert result["total"] == 2
        assert result["by_type"]["TODO"] >= 1
        assert result["by_type"]["FIXME"] >= 1


class TestCountSuppressions:
    def test_empty_dir(self, tmp_path: Path) -> None:
        result = cli._count_suppressions(tmp_path)
        assert result == {}

    def test_finds_noqa(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1  # noqa: E501\ny = 2  # type: ignore\n", encoding="utf-8")
        result = cli._count_suppressions(tmp_path)
        assert result.get("noqa", 0) >= 1
        assert result.get("type_ignore", 0) >= 1


class TestCountLintViolations:
    def test_returns_error_when_ruff_unavailable(self, tmp_path: Path, monkeypatch) -> None:
        def _fail_run(*_args, **_kwargs):
            return subprocess.CompletedProcess(args=[], returncode=1, stdout="not json", stderr="")

        monkeypatch.setattr(cli, "_run_tool", _fail_run)
        result = cli._count_lint_violations(tmp_path)
        assert "error" in result

    def test_clean_dir(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "clean.py").write_text("x = 1\n", encoding="utf-8")

        def _clean_run(*_args, **_kwargs):
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        monkeypatch.setattr(cli, "_run_tool", _clean_run)
        result = cli._count_lint_violations(tmp_path)
        assert result == {"total": 0, "by_category": {}}


class TestCheckCoverage:
    def test_no_coverage_file(self, tmp_path: Path) -> None:
        result = cli._check_coverage(tmp_path)
        assert result["available"] is False

    def test_with_invalid_coverage(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".coverage").write_text("not valid", encoding="utf-8")

        def _fail_run(*_args, **_kwargs):
            return subprocess.CompletedProcess(args=[], returncode=1, stdout="not json", stderr="")

        monkeypatch.setattr(cli, "_run_tool", _fail_run)
        result = cli._check_coverage(tmp_path)
        assert result.get("available") is False or "error" in result


class TestCheckOutdatedDeps:
    def test_no_pyproject(self, tmp_path: Path) -> None:
        result = cli._check_outdated_deps(tmp_path)
        assert result["available"] is False


class TestAssessCommand:
    @staticmethod
    def _stub_run_tool(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    def test_json_output(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "app.py").write_text("# TODO: fix\nx = 1\n", encoding="utf-8")
        monkeypatch.setattr(cli, "_run_tool", self._stub_run_tool)
        result = runner.invoke(cli.app, ["assess", "--root", str(tmp_path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "lint" in data
        assert "todos" in data
        assert "complexity" in data
        assert "coverage" in data
        assert "dependencies" in data
        assert "suppressions" in data

    def test_human_output(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(cli, "_run_tool", self._stub_run_tool)
        result = runner.invoke(cli.app, ["assess", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "Codebase Metrics" in result.output
