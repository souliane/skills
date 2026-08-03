"""Tests for the assess command in ac-reviewing-codebase CLI."""

import importlib.util
import json
import subprocess
from pathlib import Path

from _gitutil import init_repo, run_git
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

    def test_total_always_equals_the_sum_of_its_buckets(self, tmp_path: Path) -> None:
        # A line naming several markers used to increment every bucket while
        # `total` counted the line once, so the two halves of the same metric
        # disagreed (12 vs 22 on this repo) and neither was the real number.
        (tmp_path / "app.py").write_text(
            'MARKERS = {"TODO": 0, "FIXME": 0, "HACK": 0, "XXX": 0}\n# TODO: a real one\n',
            encoding="utf-8",
        )
        result = cli._count_todos(tmp_path)
        assert result["total"] == sum(result["by_type"].values())

    def test_a_line_counts_once_under_its_first_marker(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("# TODO then FIXME on one line\n", encoding="utf-8")
        result = cli._count_todos(tmp_path)
        assert result["total"] == 1
        assert result["by_type"] == {"TODO": 1}

    def test_marker_inside_a_longer_word_is_not_a_todo(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("VALID_XXXY = 1\nclass TODOList:\n    pass\n", encoding="utf-8")
        assert cli._count_todos(tmp_path)["total"] == 0


class TestCountSuppressions:
    def test_empty_dir(self, tmp_path: Path) -> None:
        result = cli._count_suppressions(tmp_path)
        assert result == {}

    def test_finds_noqa(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1  # noqa: E501\ny = 2  # type: ignore\n", encoding="utf-8")
        result = cli._count_suppressions(tmp_path)
        assert result.get("noqa", 0) >= 1
        assert result.get("type_ignore", 0) >= 1

    def test_a_quoted_marker_is_a_mention_not_a_suppression(self, tmp_path: Path) -> None:
        # A tool that reasons about suppressions names them in its own pattern
        # table. Counting those made every such repo look like it was drowning.
        (tmp_path / "app.py").write_text('PATTERNS = {"noqa": "# noqa"}\n', encoding="utf-8")
        assert cli._count_suppressions(tmp_path) == {}


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


def _git_add_commit(root: Path) -> None:
    run_git(root, "add", "-A")
    run_git(root, "commit", "-qm", "init")


class TestRepoScopedScanning:
    """F3: scans count only git-tracked files.

    Vendored ``.venv`` and nested agent worktrees must not inflate counts.
    """

    def test_todos_count_only_tracked_files(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        (tmp_path / "app.py").write_text("# TODO: tracked\n", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(".venv/\n.claude/\n", encoding="utf-8")
        _git_add_commit(tmp_path)
        # Phantom copies that must NOT be counted:
        venv = tmp_path / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "vendor.py").write_text("# TODO: vendored\n# FIXME: vendored\n", encoding="utf-8")
        wt = tmp_path / ".claude" / "worktrees" / "agent-x"
        wt.mkdir(parents=True)
        (wt / "copy.py").write_text("# TODO: worktree\n# XXX: worktree\n", encoding="utf-8")
        result = cli._count_todos(tmp_path)
        assert result["total"] == 1, f"expected only the tracked TODO, got {result}"

    def test_suppressions_count_only_tracked_files(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        (tmp_path / "app.py").write_text("x = 1  # noqa: E501\n", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(".venv/\n", encoding="utf-8")
        _git_add_commit(tmp_path)
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "vendor.py").write_text("a = 1  # noqa\nb = 2  # noqa\nc = 3  # noqa\n", encoding="utf-8")
        result = cli._count_suppressions(tmp_path)
        assert result.get("noqa", 0) == 1, f"expected only the tracked noqa, got {result}"


class TestOutdatedDepsRepoScoped:
    """F2: dependency check reflects the target repo's venv.

    It must never fall back to the assessor's own environment (which would
    yield identical false hits in every repo).
    """

    def test_no_repo_venv_is_unavailable_not_assessor_deps(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

        def _boom(*_a, **_k):
            msg = "must not shell out to the assessor's own environment"
            raise AssertionError(msg)

        monkeypatch.setattr(cli, "_run_tool", _boom)
        result = cli._check_outdated_deps(tmp_path)
        assert result["available"] is False


class TestCoverageNoDevStdout:
    """F4: coverage json -o /dev/stdout fails on real repos; use a temp file."""

    def test_does_not_use_dev_stdout(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".coverage").write_text("x", encoding="utf-8")
        captured: dict = {}

        def _capture(args, **_kwargs):
            captured["args"] = args
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="")

        monkeypatch.setattr(cli, "_run_tool", _capture)
        cli._check_coverage(tmp_path)
        assert "/dev/stdout" not in captured.get("args", []), captured


class TestUnresolvableManagedRepos:
    """MANAGED_REPOS is a regex, so a dead repo just stops matching, silently.

    Two repos stayed listed for months after being deleted: they contributed no
    rows to `status` and no warning anywhere, so nothing ever said the config
    had drifted off the disk.
    """

    def _workspace(self, tmp_path: Path, *repos: str) -> Path:
        for repo in repos:
            (tmp_path / repo / ".git").mkdir(parents=True)
        return tmp_path

    def test_reports_alternation_members_with_no_repo_on_disk(self, tmp_path: Path, monkeypatch) -> None:
        self._workspace(tmp_path, "org/alive")
        monkeypatch.setattr(cli, "_get_workspace_dir", lambda: tmp_path)
        assert cli.unresolvable_managed_repos({"MANAGED_REPOS": r"org/(alive|deleted)$"}) == ["org/deleted"]

    def test_reports_bare_literal_branches_too(self, tmp_path: Path, monkeypatch) -> None:
        self._workspace(tmp_path)
        monkeypatch.setattr(cli, "_get_workspace_dir", lambda: tmp_path)
        missing = cli.unresolvable_managed_repos({"MANAGED_REPOS": r"org/(a)$|other/solo$"})
        assert missing == ["org/a", "other/solo"]

    def test_silent_when_every_named_repo_exists(self, tmp_path: Path, monkeypatch) -> None:
        self._workspace(tmp_path, "org/a", "org/b", "other/solo")
        monkeypatch.setattr(cli, "_get_workspace_dir", lambda: tmp_path)
        assert cli.unresolvable_managed_repos({"MANAGED_REPOS": r"org/(a|b)$|other/solo$"}) == []

    def test_unset_config_names_nothing(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(cli, "_get_workspace_dir", lambda: tmp_path)
        assert cli.unresolvable_managed_repos({}) == []
