"""Tests for ac-managing-repos CLI."""

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

CLI_PATH = Path(__file__).resolve().parents[2] / "ac-managing-repos" / "scripts" / "cli.py"
SPEC = importlib.util.spec_from_file_location("managing_repos_cli", CLI_PATH)
assert SPEC is not None
assert SPEC.loader is not None
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def _git_binary() -> str:
    git = shutil.which("git")
    assert git is not None
    return git


GIT = _git_binary()


def _run_git(cwd: Path, *args: str) -> None:
    subprocess.run([GIT, *args], cwd=cwd, check=True, capture_output=True, text=True)  # noqa: S603


def _init_repo(path: Path) -> Path:
    """Create a minimal git repo with one commit."""
    path.mkdir(parents=True, exist_ok=True)
    _run_git(path, "init", "-b", "main")
    _run_git(path, "config", "user.email", "test@test.com")
    _run_git(path, "config", "user.name", "Test")
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    _run_git(path, "add", ".")
    _run_git(path, "commit", "-m", "init")
    return path


def _write_config(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _parse_shell_config
# ---------------------------------------------------------------------------


class TestParseShellConfig:
    def test_parses_key_value(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path / "cfg", 'FOO=bar\nBAZ="quoted"\n')
        result = cli._parse_shell_config(cfg)
        assert result == {"FOO": "bar", "BAZ": "quoted"}

    def test_skips_comments_and_blanks(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path / "cfg", "# comment\n\nKEY=val\n")
        result = cli._parse_shell_config(cfg)
        assert result == {"KEY": "val"}

    def test_skips_lines_without_equals(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path / "cfg", "no-equals-here\nKEY=val\n")
        result = cli._parse_shell_config(cfg)
        assert result == {"KEY": "val"}

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        assert cli._parse_shell_config(tmp_path / "nonexistent") == {}

    def test_strips_single_quotes(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path / "cfg", "KEY='single'\n")
        result = cli._parse_shell_config(cfg)
        assert result == {"KEY": "single"}

    def test_handles_value_with_equals(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path / "cfg", "KEY=a=b=c\n")
        result = cli._parse_shell_config(cfg)
        assert result == {"KEY": "a=b=c"}


# ---------------------------------------------------------------------------
# _expand
# ---------------------------------------------------------------------------


class TestExpand:
    def test_expands_home(self) -> None:
        result = cli._expand("$HOME/workspace")
        assert result == f"{Path.home()}/workspace"

    def test_expands_tilde(self) -> None:
        result = cli._expand("~/workspace")
        assert result == f"{Path.home()}/workspace"

    def test_no_expansion_needed(self) -> None:
        assert cli._expand("/absolute/path") == "/absolute/path"


# ---------------------------------------------------------------------------
# _scan_repos
# ---------------------------------------------------------------------------


class TestScanRepos:
    def test_finds_matching_repos(self, tmp_path: Path) -> None:
        workspace = tmp_path / "ws"
        _init_repo(workspace / "org" / "repo-a")
        _init_repo(workspace / "org" / "repo-b")
        _init_repo(workspace / "org" / "unrelated")
        workspace.mkdir(parents=True, exist_ok=True)

        repos = cli._scan_repos(workspace, r"org/(repo-a|repo-b)$")
        names = [r.name for r in repos]
        assert "repo-a" in names
        assert "repo-b" in names
        assert "unrelated" not in names

    def test_returns_empty_when_no_match(self, tmp_path: Path) -> None:
        workspace = tmp_path / "ws"
        _init_repo(workspace / "org" / "other")
        workspace.mkdir(parents=True, exist_ok=True)

        repos = cli._scan_repos(workspace, r"org/nonexistent$")
        assert repos == []

    def test_respects_depth_limit(self, tmp_path: Path) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir(parents=True, exist_ok=True)
        # Create a repo at depth 4 (beyond MAX_SCAN_DEPTH=3)
        deep = workspace / "a" / "b" / "c" / "d"
        _init_repo(deep)

        repos = cli._scan_repos(workspace, r"d$")
        assert repos == []

    def test_stops_recursing_into_matched_repos(self, tmp_path: Path) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir(parents=True, exist_ok=True)
        parent = _init_repo(workspace / "org" / "parent")
        # Nested git repo inside parent
        _init_repo(parent / "nested")

        repos = cli._scan_repos(workspace, r"org/parent$")
        names = [r.name for r in repos]
        assert names == ["parent"]


# ---------------------------------------------------------------------------
# parse_boilerplate_map
# ---------------------------------------------------------------------------


class TestParseBoilerplateMap:
    def test_parses_valid_map(self) -> None:
        config = {"BOILERPLATE_MAP": "bp1:dep-a,dep-b;bp2:dep-c"}
        result = cli.parse_boilerplate_map(config)
        assert result == {"bp1": ["dep-a", "dep-b"], "bp2": ["dep-c"]}

    def test_returns_empty_when_missing(self) -> None:
        assert cli.parse_boilerplate_map({}) == {}

    def test_returns_empty_for_empty_string(self) -> None:
        assert cli.parse_boilerplate_map({"BOILERPLATE_MAP": ""}) == {}

    def test_skips_entries_without_colon(self) -> None:
        config = {"BOILERPLATE_MAP": "valid:dep;no-colon;also-valid:x"}
        result = cli.parse_boilerplate_map(config)
        assert result == {"valid": ["dep"], "also-valid": ["x"]}

    def test_handles_whitespace(self) -> None:
        config = {"BOILERPLATE_MAP": " bp1 : dep-a , dep-b ; bp2 : dep-c "}
        result = cli.parse_boilerplate_map(config)
        assert result == {"bp1": ["dep-a", "dep-b"], "bp2": ["dep-c"]}


# ---------------------------------------------------------------------------
# git helpers (integration tests with real git repos)
# ---------------------------------------------------------------------------


class TestGitHelpers:
    def test_git_output_returns_stdout(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        branch = cli.git_output(repo, "branch", "--show-current")
        assert branch in {"main", "master"}

    def test_git_ok_returns_true_for_valid_command(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        assert cli.git_ok(repo, "status") is True

    def test_git_ok_returns_false_for_invalid_ref(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        assert cli.git_ok(repo, "rev-parse", "--verify", "nonexistent") is False

    def test_get_unpushed_no_upstream(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        result = cli.get_unpushed(repo)
        assert len(result) == 1
        assert result[0].startswith("(no upstream")

    def test_get_dirty_count_clean(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        assert cli.get_dirty_count(repo) == 0

    def test_get_dirty_count_with_changes(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        (repo / "new.txt").write_text("dirty", encoding="utf-8")
        assert cli.get_dirty_count(repo) == 1

    def test_get_stale_branches_none_on_fresh_repo(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        assert cli.get_stale_branches(repo) == []

    def test_get_stale_branches_detects_merged(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _run_git(repo, "checkout", "-b", "feature")
        (repo / "feat.txt").write_text("x", encoding="utf-8")
        _run_git(repo, "add", ".")
        _run_git(repo, "commit", "-m", "feat")
        _run_git(repo, "checkout", "main")
        _run_git(repo, "merge", "feature")
        stale = cli.get_stale_branches(repo)
        assert "feature" in stale


# ---------------------------------------------------------------------------
# _build_repo_status / _format_status
# ---------------------------------------------------------------------------


class TestBuildAndFormatStatus:
    def test_clean_repo(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        # Add a remote so there's an upstream
        _run_git(repo, "remote", "add", "origin", str(tmp_path / "fake-remote"))
        info = cli._build_repo_status(repo)
        assert info["dirty"] == 0
        assert info["stale"] == []
        # No upstream tracking, so no_upstream is True
        assert info["no_upstream"] is True

    def test_dirty_repo(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        (repo / "dirty.txt").write_text("x", encoding="utf-8")
        info = cli._build_repo_status(repo)
        assert info["dirty"] == 1

    def test_format_clean(self) -> None:
        info = {"n_unpushed": 0, "dirty": 0, "stale": [], "no_upstream": False}
        assert cli._format_status(info) == "[green]clean[/green]"

    def test_format_needs_push(self) -> None:
        info = {"n_unpushed": 2, "dirty": 0, "stale": [], "no_upstream": False}
        assert "needs push" in cli._format_status(info)

    def test_format_dirty(self) -> None:
        info = {"n_unpushed": 0, "dirty": 3, "stale": [], "no_upstream": False}
        assert "dirty" in cli._format_status(info)

    def test_format_no_upstream(self) -> None:
        info = {"n_unpushed": 0, "dirty": 0, "stale": [], "no_upstream": True}
        assert "no upstream" in cli._format_status(info)

    def test_format_stale(self) -> None:
        info = {"n_unpushed": 0, "dirty": 0, "stale": ["old-branch"], "no_upstream": False}
        assert "stale" in cli._format_status(info)

    def test_format_combined(self) -> None:
        info = {"n_unpushed": 1, "dirty": 2, "stale": ["x"], "no_upstream": False}
        result = cli._format_status(info)
        assert "needs push" in result
        assert "dirty" in result
        assert "stale" in result


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------


class TestTruncate:
    def test_short_string_unchanged(self) -> None:
        assert cli._truncate("hello", 10) == "hello"

    def test_exact_length_unchanged(self) -> None:
        assert cli._truncate("12345", 5) == "12345"

    def test_long_string_truncated(self) -> None:
        result = cli._truncate("a very long string indeed", 10)
        assert len(result) == 10
        assert result.endswith("...")


# ---------------------------------------------------------------------------
# _expand_env
# ---------------------------------------------------------------------------


class TestExpandEnv:
    def test_expands_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MY_CUSTOM_VAR", raising=False)
        result = cli._expand_env("${MY_CUSTOM_VAR:-~/.fallback}/data")
        assert str(Path.home()) in result
        assert result.endswith(".fallback/data")

    def test_expands_env_var_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_CUSTOM_VAR", "/custom/path")
        result = cli._expand_env("${MY_CUSTOM_VAR:-~/.fallback}/data")
        assert result == "/custom/path/data"


# ---------------------------------------------------------------------------
# _dir_size
# ---------------------------------------------------------------------------


class TestDirSize:
    def test_empty_dir(self, tmp_path: Path) -> None:
        assert cli._dir_size(tmp_path) == "0 B"

    def test_small_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        result = cli._dir_size(tmp_path)
        assert "B" in result

    def test_nested_files(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "big.bin").write_bytes(b"\x00" * 2048)
        result = cli._dir_size(tmp_path)
        assert "KB" in result
