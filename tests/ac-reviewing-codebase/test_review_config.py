"""Tests for reading ~/.ac-reviewing-codebase and judging whether it still matches disk."""

from pathlib import Path

from _cli_import import load

review_config = load("review_config")


def _write_config(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class TestParseShellConfig:
    def test_parses_key_value(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path / "cfg", 'FOO=bar\nBAZ="quoted"\n')
        assert review_config.parse_shell_config(cfg) == {"FOO": "bar", "BAZ": "quoted"}

    def test_skips_comments_and_blanks(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path / "cfg", "# comment\n\nKEY=val\n")
        assert review_config.parse_shell_config(cfg) == {"KEY": "val"}

    def test_skips_lines_without_equals(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path / "cfg", "no-equals-here\nKEY=val\n")
        assert review_config.parse_shell_config(cfg) == {"KEY": "val"}

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        assert review_config.parse_shell_config(tmp_path / "nonexistent") == {}

    def test_strips_single_quotes(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path / "cfg", "KEY='single'\n")
        assert review_config.parse_shell_config(cfg) == {"KEY": "single"}

    def test_handles_value_with_equals(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path / "cfg", "KEY=a=b=c\n")
        assert review_config.parse_shell_config(cfg) == {"KEY": "a=b=c"}


class TestExpand:
    def test_expands_home(self) -> None:
        assert review_config.expand("$HOME/workspace") == f"{Path.home()}/workspace"

    def test_expands_leading_tilde(self) -> None:
        assert review_config.expand("~/workspace") == f"{Path.home()}/workspace"

    def test_no_expansion_needed(self) -> None:
        assert review_config.expand("/absolute/path") == "/absolute/path"

    def test_non_leading_tilde_is_literal(self) -> None:
        # A ``~`` mid-value (e.g. a backup-file suffix) must not be expanded.
        assert review_config.expand("uv.lock~") == "uv.lock~"
        assert review_config.expand("/a/b~c") == "/a/b~c"


class TestParseBoilerplateMap:
    def test_parses_valid_map(self) -> None:
        config = {"BOILERPLATE_MAP": "bp1:dep-a,dep-b;bp2:dep-c"}
        assert review_config.parse_boilerplate_map(config) == {"bp1": ["dep-a", "dep-b"], "bp2": ["dep-c"]}

    def test_returns_empty_when_missing(self) -> None:
        assert review_config.parse_boilerplate_map({}) == {}

    def test_returns_empty_for_empty_string(self) -> None:
        assert review_config.parse_boilerplate_map({"BOILERPLATE_MAP": ""}) == {}

    def test_skips_entries_without_colon(self) -> None:
        config = {"BOILERPLATE_MAP": "valid:dep;no-colon;also-valid:x"}
        assert review_config.parse_boilerplate_map(config) == {"valid": ["dep"], "also-valid": ["x"]}

    def test_handles_whitespace(self) -> None:
        config = {"BOILERPLATE_MAP": " bp1 : dep-a , dep-b ; bp2 : dep-c "}
        assert review_config.parse_boilerplate_map(config) == {"bp1": ["dep-a", "dep-b"], "bp2": ["dep-c"]}


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
        monkeypatch.setattr(review_config, "get_workspace_dir", lambda: tmp_path)
        assert review_config.unresolvable_managed_repos({"MANAGED_REPOS": r"org/(alive|deleted)$"}) == ["org/deleted"]

    def test_reports_bare_literal_branches_too(self, tmp_path: Path, monkeypatch) -> None:
        self._workspace(tmp_path)
        monkeypatch.setattr(review_config, "get_workspace_dir", lambda: tmp_path)
        missing = review_config.unresolvable_managed_repos({"MANAGED_REPOS": r"org/(a)$|other/solo$"})
        assert missing == ["org/a", "other/solo"]

    def test_silent_when_every_named_repo_exists(self, tmp_path: Path, monkeypatch) -> None:
        self._workspace(tmp_path, "org/a", "org/b", "other/solo")
        monkeypatch.setattr(review_config, "get_workspace_dir", lambda: tmp_path)
        assert review_config.unresolvable_managed_repos({"MANAGED_REPOS": r"org/(a|b)$|other/solo$"}) == []

    def test_unset_config_names_nothing(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(review_config, "get_workspace_dir", lambda: tmp_path)
        assert review_config.unresolvable_managed_repos({}) == []


class TestConfigHealthIssues:
    def test_unset_keys_are_reported(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(review_config, "get_workspace_dir", lambda: tmp_path)
        issues = review_config.config_health_issues({})
        assert any("MANAGED_REPOS" in i for i in issues)
        assert any("MAINTAINED_SKILLS" in i for i in issues)

    def test_a_fully_resolvable_config_is_silent(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "org" / "a" / ".git").mkdir(parents=True)
        monkeypatch.setattr(review_config, "get_workspace_dir", lambda: tmp_path)
        config = {"MANAGED_REPOS": r"org/(a)$", "MAINTAINED_SKILLS": "org/a"}
        assert review_config.config_health_issues(config) == []
