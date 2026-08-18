"""Tests for the deterministic metrics behind the ``assess`` command."""

import json
import subprocess
from pathlib import Path

from _cli_import import load
from _gitutil import init_repo, run_git

metrics = load("codebase_metrics")
vendored_paths = load("vendored_paths")

NOTHING = vendored_paths.VendoredPaths()
VENDOR = vendored_paths.VendoredPaths(("vendor",), "test")


class TestCountTodos:
    def test_empty_dir(self, tmp_path: Path) -> None:
        result = metrics.count_todos(tmp_path, NOTHING)
        assert result["total"] == 0

    def test_finds_todos(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("# TODO: fix this\n# FIXME: broken\n", encoding="utf-8")
        result = metrics.count_todos(tmp_path, NOTHING)
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
        result = metrics.count_todos(tmp_path, NOTHING)
        assert result["total"] == sum(result["by_type"].values())

    def test_a_line_counts_once_under_its_first_marker(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("# TODO then FIXME on one line\n", encoding="utf-8")
        result = metrics.count_todos(tmp_path, NOTHING)
        assert result["total"] == 1
        assert result["by_type"] == {"TODO": 1}

    def test_marker_inside_a_longer_word_is_not_a_todo(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("VALID_XXXY = 1\nclass TODOList:\n    pass\n", encoding="utf-8")
        assert metrics.count_todos(tmp_path, NOTHING)["total"] == 0


class TestCountLintViolations:
    def test_returns_error_when_ruff_unavailable(self, tmp_path: Path, monkeypatch) -> None:
        def _fail_run(*_args, **_kwargs):
            return subprocess.CompletedProcess(args=[], returncode=1, stdout="not json", stderr="")

        monkeypatch.setattr(metrics, "run_tool", _fail_run)
        result = metrics.count_lint_violations(tmp_path)
        assert "error" in result

    def test_clean_dir(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "clean.py").write_text("x = 1\n", encoding="utf-8")

        def _clean_run(*_args, **_kwargs):
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        monkeypatch.setattr(metrics, "run_tool", _clean_run)
        result = metrics.count_lint_violations(tmp_path)
        assert result == {"total": 0, "by_category": {}}


class TestCheckCoverage:
    def test_no_coverage_file(self, tmp_path: Path) -> None:
        result = metrics.check_coverage(tmp_path, NOTHING)
        assert result["available"] is False

    def test_with_invalid_coverage(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".coverage").write_text("not valid", encoding="utf-8")

        def _fail_run(*_args, **_kwargs):
            return subprocess.CompletedProcess(args=[], returncode=1, stdout="not json", stderr="")

        monkeypatch.setattr(metrics, "run_tool", _fail_run)
        result = metrics.check_coverage(tmp_path, NOTHING)
        assert result.get("available") is False or "error" in result


_COVERED_FILE = {"summary": {"num_statements": 8, "num_branches": 2, "covered_lines": 8, "covered_branches": 2}}
_UNCOVERED_FILE = {"summary": {"num_statements": 10, "num_branches": 0, "covered_lines": 0, "covered_branches": 0}}


class TestAssessingDoesNotMutate:
    """Measuring a repo must never change it.

    `[tool.ruff] fix = true` is a common setting; without `--no-fix` the lint
    metric REWRITES the tree it was asked to measure. This silently edited four
    unrelated files in this very repo before it was caught.
    """

    SOURCE = "import os\nimport sys\n\nx = 1\n"

    def test_lint_metric_leaves_a_fix_true_repo_untouched(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.ruff]\nfix = true\nlint.select = ["F"]\n', encoding="utf-8")
        (tmp_path / "app.py").write_text(self.SOURCE, encoding="utf-8")
        metrics.count_lint_violations(tmp_path)
        assert (tmp_path / "app.py").read_text(encoding="utf-8") == self.SOURCE

    def test_complexity_metric_leaves_a_fix_true_repo_untouched(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.ruff]\nfix = true\nlint.select = ["F"]\n', encoding="utf-8")
        (tmp_path / "app.py").write_text(self.SOURCE, encoding="utf-8")
        metrics.count_complexity(tmp_path)
        assert (tmp_path / "app.py").read_text(encoding="utf-8") == self.SOURCE


class TestCoverageScopes:
    """A coverage number invites a false "regressed" read until it says what it covers."""

    @staticmethod
    def _payload(*, with_vendored: bool = True) -> dict:
        files = {"src/app.py": _COVERED_FILE}
        if with_vendored:
            files["vendor/dep.py"] = _UNCOVERED_FILE
        return {"totals": {"percent_covered": 50.0}, "files": files}

    def _stub_coverage(self, monkeypatch, payload: dict) -> None:
        def _write(args, **_kwargs):
            Path(args[-1]).write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(metrics, "run_tool", _write)

    def test_each_scope_reports_its_own_percentage_and_file_count(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".coverage").write_text("x", encoding="utf-8")
        self._stub_coverage(monkeypatch, self._payload())
        scopes = metrics.check_coverage(tmp_path, VENDOR)["scopes"]
        assert scopes["first_party"] == {"files": 1, "measured": 10, "percent": 100.0}
        assert scopes["vendored"] == {"files": 1, "measured": 10, "percent": 0.0}

    def test_an_unmeasured_scope_reports_none_not_zero_percent(self, tmp_path: Path, monkeypatch) -> None:
        # "0%" would read as "tested and failing"; nothing was measured at all.
        (tmp_path / ".coverage").write_text("x", encoding="utf-8")
        self._stub_coverage(monkeypatch, self._payload(with_vendored=False))
        assert metrics.check_coverage(tmp_path, VENDOR)["scopes"]["vendored"]["percent"] is None

    def test_a_failed_coverage_json_says_why_instead_of_blaming_a_missing_file(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        (tmp_path / ".coverage").write_text("x", encoding="utf-8")

        def _fail(args, **_kwargs):
            reason = "No source for code: gone.py\n"
            return subprocess.CompletedProcess(args=args, returncode=1, stdout=reason, stderr="")

        monkeypatch.setattr(metrics, "run_tool", _fail)
        result = metrics.check_coverage(tmp_path, NOTHING)
        assert result["available"] is False
        assert "No source for code" in str(result["error"])


class TestCheckOutdatedDeps:
    def test_no_pyproject(self, tmp_path: Path) -> None:
        result = metrics.check_outdated_deps(tmp_path)
        assert result["available"] is False


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
        result = metrics.count_todos(tmp_path, NOTHING)
        assert result["total"] == 1, f"expected only the tracked TODO, got {result}"

    def test_todos_are_split_first_party_from_vendored(self, tmp_path: Path) -> None:
        init_repo(tmp_path)
        (tmp_path / "app.py").write_text("# TODO: ours\n", encoding="utf-8")
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "dep.py").write_text("# TODO: theirs\n# FIXME: theirs\n", encoding="utf-8")
        _git_add_commit(tmp_path)
        result = metrics.count_todos(tmp_path, VENDOR)
        assert result["total"] == 3
        assert result["scopes"] == {"first_party": 1, "vendored": 2}


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

        monkeypatch.setattr(metrics, "run_tool", _boom)
        result = metrics.check_outdated_deps(tmp_path)
        assert result["available"] is False


class TestCoverageNoDevStdout:
    """F4: coverage json -o /dev/stdout fails on real repos; use a temp file."""

    def test_does_not_use_dev_stdout(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / ".coverage").write_text("x", encoding="utf-8")
        captured: dict = {}

        def _capture(args, **_kwargs):
            captured["args"] = args
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="")

        monkeypatch.setattr(metrics, "run_tool", _capture)
        metrics.check_coverage(tmp_path, NOTHING)
        assert "/dev/stdout" not in captured.get("args", []), captured


class TestCollect:
    def test_reports_every_metric_family(self, tmp_path: Path, monkeypatch) -> None:
        def _stub(*_a, **_k):
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        monkeypatch.setattr(metrics, "run_tool", _stub)
        assert set(metrics.collect(tmp_path)) == {
            "vendored",
            "lint",
            "todos",
            "complexity",
            "coverage",
            "dependencies",
            "suppressions",
        }
