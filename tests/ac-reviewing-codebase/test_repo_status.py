"""Tests for repo discovery and the per-repo delivery status read from git."""

from pathlib import Path

from _cli_import import load
from _gitutil import init_repo, run_git

repo_status = load("repo_status")


def _init_repo(path: Path) -> Path:
    """Create a minimal git repo with one commit."""
    init_repo(path)
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    run_git(path, "add", ".")
    run_git(path, "commit", "-m", "init")
    return path


class TestScanRepos:
    def test_finds_matching_repos(self, tmp_path: Path) -> None:
        workspace = tmp_path / "ws"
        _init_repo(workspace / "org" / "repo-a")
        _init_repo(workspace / "org" / "repo-b")
        _init_repo(workspace / "org" / "unrelated")
        workspace.mkdir(parents=True, exist_ok=True)

        repos = repo_status.scan_repos(workspace, r"org/(repo-a|repo-b)$")
        names = [r.name for r in repos]
        assert "repo-a" in names
        assert "repo-b" in names
        assert "unrelated" not in names

    def test_returns_empty_when_no_match(self, tmp_path: Path) -> None:
        workspace = tmp_path / "ws"
        _init_repo(workspace / "org" / "other")
        workspace.mkdir(parents=True, exist_ok=True)

        repos = repo_status.scan_repos(workspace, r"org/nonexistent$")
        assert repos == []

    def test_respects_depth_limit(self, tmp_path: Path) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir(parents=True, exist_ok=True)
        # Create a repo at depth 4 (beyond MAX_SCAN_DEPTH=3)
        deep = workspace / "a" / "b" / "c" / "d"
        _init_repo(deep)

        repos = repo_status.scan_repos(workspace, r"d$")
        assert repos == []

    def test_stops_recursing_into_matched_repos(self, tmp_path: Path) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir(parents=True, exist_ok=True)
        parent = _init_repo(workspace / "org" / "parent")
        # Nested git repo inside parent
        _init_repo(parent / "nested")

        repos = repo_status.scan_repos(workspace, r"org/parent$")
        names = [r.name for r in repos]
        assert names == ["parent"]


class TestGitHelpers:
    def test_git_output_returns_stdout(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        branch = repo_status.git_output(repo, "branch", "--show-current")
        assert branch in {"main", "master"}

    def test_git_ok_returns_true_for_valid_command(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        assert repo_status.git_ok(repo, "status") is True

    def test_git_ok_returns_false_for_invalid_ref(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        assert repo_status.git_ok(repo, "rev-parse", "--verify", "nonexistent") is False

    def test_get_unpushed_no_upstream(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        result = repo_status.get_unpushed(repo)
        assert len(result) == 1
        assert result[0].startswith("(no upstream")

    def test_get_dirty_count_clean(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        assert repo_status.get_dirty_count(repo) == 0

    def test_get_dirty_count_with_changes(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        (repo / "new.txt").write_text("dirty", encoding="utf-8")
        assert repo_status.get_dirty_count(repo) == 1

    def test_get_stale_branches_none_on_fresh_repo(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        assert repo_status.get_stale_branches(repo) == []

    def test_get_stale_branches_detects_merged(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        run_git(repo, "checkout", "-b", "feature")
        (repo / "feat.txt").write_text("x", encoding="utf-8")
        run_git(repo, "add", ".")
        run_git(repo, "commit", "-m", "feat")
        run_git(repo, "checkout", "main")
        run_git(repo, "merge", "feature")
        stale = repo_status.get_stale_branches(repo)
        assert "feature" in stale


class TestBuildAndFormatStatus:
    def test_clean_repo(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        # Add a remote so there's an upstream
        run_git(repo, "remote", "add", "origin", str(tmp_path / "fake-remote"))
        info = repo_status.build_repo_status(repo)
        assert info["dirty"] == 0
        assert info["stale"] == []
        # No upstream tracking, so no_upstream is True
        assert info["no_upstream"] is True

    def test_dirty_repo(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        (repo / "dirty.txt").write_text("x", encoding="utf-8")
        info = repo_status.build_repo_status(repo)
        assert info["dirty"] == 1

    def test_format_clean(self) -> None:
        info = {"n_unpushed": 0, "dirty": 0, "stale": [], "no_upstream": False, "stashes": 0, "other_branches": []}
        assert repo_status.format_status(info) == "[green]clean[/green]"

    def test_format_needs_push(self) -> None:
        info = {"n_unpushed": 2, "dirty": 0, "stale": [], "no_upstream": False, "stashes": 0, "other_branches": []}
        assert "needs push" in repo_status.format_status(info)

    def test_format_dirty(self) -> None:
        info = {"n_unpushed": 0, "dirty": 3, "stale": [], "no_upstream": False, "stashes": 0, "other_branches": []}
        assert "dirty" in repo_status.format_status(info)

    def test_format_no_upstream(self) -> None:
        info = {"n_unpushed": 0, "dirty": 0, "stale": [], "no_upstream": True, "stashes": 0, "other_branches": []}
        assert "no upstream" in repo_status.format_status(info)

    def test_format_stale(self) -> None:
        info = {
            "n_unpushed": 0,
            "dirty": 0,
            "stale": ["old-branch"],
            "no_upstream": False,
            "stashes": 0,
            "other_branches": [],
        }
        assert "stale" in repo_status.format_status(info)

    def test_format_combined(self) -> None:
        info = {"n_unpushed": 1, "dirty": 2, "stale": ["x"], "no_upstream": False, "stashes": 0, "other_branches": []}
        result = repo_status.format_status(info)
        assert "needs push" in result
        assert "dirty" in result
        assert "stale" in result


class TestDefaultBranch:
    def test_falls_back_to_main_without_origin(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        assert repo_status.default_branch(repo) in {"main", "master"}

    def test_prefers_origin_head(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        run_git(repo, "checkout", "-b", "trunk")
        run_git(repo, "remote", "add", "origin", str(repo))
        # Point origin/HEAD at trunk without a network fetch.
        run_git(repo, "update-ref", "refs/remotes/origin/trunk", "HEAD")
        run_git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
        assert repo_status.default_branch(repo) == "trunk"
