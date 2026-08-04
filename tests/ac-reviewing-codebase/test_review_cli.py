"""Tests for the CLI surface itself: command wiring and repo-selection flags."""

import json
import subprocess
from pathlib import Path

import pytest
import typer.main
from _cli_import import load, load_cli
from _gitutil import init_repo, run_git
from typer.testing import CliRunner

cli = load_cli()
metrics = load("codebase_metrics")
repo_status = load("repo_status")
review_config = load("review_config")

runner = CliRunner()


def _option_names(command: str) -> set[str]:
    """Every flag spelling ``command`` accepts, as click sees them."""
    click_command = typer.main.get_group(cli.app).commands[command]
    return {opt for param in click_command.params for opt in param.opts}


def _skill_repo(tmp_path: Path, body: str) -> Path:
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
    run_git(tmp_path, "init")
    run_git(tmp_path, "add", ".")
    return tmp_path


class TestCheckCommand:
    def test_pass_on_clean_repo(self, tmp_path: Path) -> None:
        root = _skill_repo(tmp_path, "---\nname: demo-skill\ndescription: Demo.\nmetadata:\n  version: 0.0.1\n---\n")
        result = runner.invoke(cli.app, ["check", "--root", str(root)])
        assert result.exit_code == 0
        assert "PASS" in result.output

    def test_fail_on_errors(self, tmp_path: Path) -> None:
        root = _skill_repo(tmp_path, "# No frontmatter")
        result = runner.invoke(cli.app, ["check", "--root", str(root)])
        assert result.exit_code == 1
        assert "FAIL" in result.output


class TestAssessCommand:
    @staticmethod
    def _stub_run_tool(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    def test_json_output(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "app.py").write_text("# TODO: fix\nx = 1\n", encoding="utf-8")
        monkeypatch.setattr(metrics, "run_tool", self._stub_run_tool)
        result = runner.invoke(cli.app, ["assess", "--root", str(tmp_path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert set(data) == {"lint", "todos", "complexity", "coverage", "dependencies", "suppressions"}

    def test_human_output(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(metrics, "run_tool", self._stub_run_tool)
        result = runner.invoke(cli.app, ["assess", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "Codebase Metrics" in result.output


class TestRepoSelectionFlags:
    """One concept, one flag name.

    ``--root`` is a repository PATH on every command that takes one. ``status``
    spans every managed repo, so it narrows by directory NAME — under
    ``--name``, with the older ``--repo`` kept as an alias so existing callers
    and docs keep working.
    """

    @pytest.fixture
    def two_repos(self, tmp_path: Path, monkeypatch) -> list[Path]:
        repos = []
        for name in ("repo-a", "repo-b"):
            repo = init_repo(tmp_path / name)
            (repo / "README.md").write_text("# x\n", encoding="utf-8")
            run_git(repo, "add", ".")
            run_git(repo, "commit", "-qm", "init")
            repos.append(repo)
        monkeypatch.setattr(review_config, "load_config", lambda: {"MANAGED_REPOS": "x"})
        monkeypatch.setattr(repo_status, "discover_repos", lambda _config: repos)
        return repos

    def test_name_selects_a_single_repo(self, two_repos: list[Path]) -> None:
        result = runner.invoke(cli.app, ["status", "--name", "repo-a"])
        assert "repo-a" in result.output
        assert "repo-b" not in result.output

    def test_repo_remains_an_alias_for_name(self, two_repos: list[Path]) -> None:
        result = runner.invoke(cli.app, ["status", "--repo", "repo-a"])
        assert "repo-a" in result.output
        assert "repo-b" not in result.output

    def test_unknown_name_is_an_error_not_an_empty_table(self, two_repos: list[Path]) -> None:
        result = runner.invoke(cli.app, ["status", "--name", "repo-z"])
        assert result.exit_code == 1
        assert "No matching repos" in result.output

    def test_root_is_a_path_on_every_command_that_takes_one(self) -> None:
        for command in ("check", "assess"):
            names = _option_names(command)
            assert "--root" in names, f"{command} lost --root"
            assert "--repo" not in names, f"{command} spells a repo path --repo"

    def test_status_offers_both_spellings_of_the_name_filter(self) -> None:
        names = _option_names("status")
        assert {"--name", "-n", "--repo", "-r"} <= names
        assert "--root" not in names, "status selects by name, not by path"
