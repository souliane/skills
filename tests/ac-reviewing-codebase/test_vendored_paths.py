"""Tests for deciding which paths hold somebody else's code.

The whole point is that the answer is READ from the repo, never hardcoded: a
metric split on a guessed path is as misleading as no split at all.
"""

from pathlib import Path

import pytest
from _cli_import import load
from _gitutil import init_repo, run_git

vendored_paths = load("vendored_paths")


def _commit(root: Path) -> None:
    run_git(root, "add", "-A")
    run_git(root, "commit", "-qm", "init")


def _repo_with(tmp_path: Path, files: dict[str, str], *, gitignore: str = "") -> Path:
    init_repo(tmp_path)
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    if gitignore:
        (tmp_path / ".gitignore").write_text(gitignore, encoding="utf-8")
    _commit(tmp_path)
    return tmp_path


class TestResolve:
    def test_gitattributes_vendored_marker_wins_over_convention(self, tmp_path: Path) -> None:
        root = _repo_with(
            tmp_path,
            {
                ".gitattributes": "upstream/** linguist-vendored\n",
                "upstream/lib.py": "x = 1\n",
                "vendor/other.py": "y = 2\n",
            },
        )
        resolved = vendored_paths.resolve(root)
        assert resolved.prefixes == ("upstream",)
        assert ".gitattributes" in resolved.source

    def test_unset_vendored_attribute_does_not_mark_a_path(self, tmp_path: Path) -> None:
        root = _repo_with(
            tmp_path,
            {".gitattributes": "upstream/** -linguist-vendored\n", "upstream/lib.py": "x = 1\n"},
        )
        assert vendored_paths.resolve(root).prefixes == ()

    def test_ruff_exclude_declares_what_the_repo_does_not_own(self, tmp_path: Path) -> None:
        root = _repo_with(
            tmp_path,
            {
                "pyproject.toml": '[tool.ruff]\nextend-exclude = ["upstream"]\n',
                "upstream/core.py": "x = 1\n",
                "src/app.py": "y = 2\n",
            },
        )
        resolved = vendored_paths.resolve(root)
        assert resolved.prefixes == ("upstream",)
        assert resolved.source == "ruff exclude (pyproject.toml)"

    def test_a_standalone_ruff_config_is_read_and_wins_as_ruff_reads_it(self, tmp_path: Path) -> None:
        # ruff uses the FIRST config it finds and ignores the rest. Reading
        # only pyproject.toml would miss the exclusion entirely and report a
        # tree ruff never lints as this repo's own code.
        root = _repo_with(
            tmp_path,
            {
                ".ruff.toml": 'extend-exclude = ["upstream"]\n',
                "pyproject.toml": '[tool.ruff]\nextend-exclude = ["src"]\n',
                "upstream/core.py": "x = 1\n",
                "src/app.py": "y = 2\n",
            },
        )
        resolved = vendored_paths.resolve(root)
        assert resolved.prefixes == ("upstream",)
        assert resolved.source == "ruff exclude (.ruff.toml)"

    def test_an_excluded_but_untracked_dir_is_not_vendored_code(self, tmp_path: Path) -> None:
        # `.venv`/`build` land in every ruff exclude list and are nobody's
        # source. Calling them vendored attaches a label to a directory that
        # contributes no numbers at all.
        root = _repo_with(
            tmp_path,
            {
                "pyproject.toml": '[tool.ruff]\nextend-exclude = ["build", "upstream"]\n',
                "upstream/core.py": "x = 1\n",
            },
            gitignore="build/\n",
        )
        (root / "build").mkdir()
        (root / "build" / "out.py").write_text("z = 3\n", encoding="utf-8")
        assert vendored_paths.resolve(root).prefixes == ("upstream",)

    def test_conventional_vendor_directory_is_the_fallback(self, tmp_path: Path) -> None:
        root = _repo_with(tmp_path, {"vendor/dep.py": "x = 1\n", "src/app.py": "y = 2\n"})
        resolved = vendored_paths.resolve(root)
        assert resolved.prefixes == ("vendor",)
        assert "convention" in resolved.source

    def test_explicit_override_beats_every_detection(self, tmp_path: Path) -> None:
        root = _repo_with(tmp_path, {"vendor/dep.py": "x = 1\n", "upstream/core.py": "y = 2\n"})
        resolved = vendored_paths.resolve(root, ["upstream"])
        assert resolved.prefixes == ("upstream",)
        assert resolved.source == "--vendored"

    def test_a_repo_that_declares_nothing_gets_no_split(self, tmp_path: Path) -> None:
        root = _repo_with(tmp_path, {"src/app.py": "x = 1\n"})
        resolved = vendored_paths.resolve(root)
        assert resolved.prefixes == ()
        assert resolved.declared is False

    def test_malformed_pyproject_does_not_crash_the_assessment(self, tmp_path: Path) -> None:
        root = _repo_with(tmp_path, {"pyproject.toml": "[tool.ruff\nbroken", "src/app.py": "x = 1\n"})
        assert vendored_paths.resolve(root).prefixes == ()


class TestNormalize:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("vendor", ("vendor",)),
            ("./vendor", ("vendor",)),
            ("/vendor/", ("vendor",)),
            ("vendor/**", ("vendor",)),
            ("vendor/*", ("vendor",)),
            ("*.py", ()),
            ("", ()),
        ],
    )
    def test_config_spellings_reduce_to_one_prefix(self, raw: str, expected: tuple[str, ...]) -> None:
        assert vendored_paths._normalize([raw]) == expected

    def test_duplicate_spellings_collapse(self) -> None:
        assert vendored_paths._normalize(["vendor", "vendor/**", "./vendor"]) == ("vendor",)


class TestCovers:
    @pytest.mark.parametrize(
        ("path", "is_vendored"),
        [
            ("vendor", True),
            ("vendor/teatree/src/a.py", True),
            ("vendors/a.py", False),
            ("src/vendor/a.py", False),
            ("src/a.py", False),
        ],
    )
    def test_only_paths_under_the_prefix_are_vendored(self, path: str, *, is_vendored: bool) -> None:
        assert vendored_paths.VendoredPaths(("vendor",)).covers(path) is is_vendored

    def test_scope_names_are_the_ones_the_report_uses(self) -> None:
        paths = vendored_paths.VendoredPaths(("vendor",))
        assert paths.scope_of("vendor/a.py") == vendored_paths.VENDORED
        assert paths.scope_of("src/a.py") == vendored_paths.FIRST_PARTY


class TestLabel:
    def test_the_vendored_label_names_the_paths_it_covers(self) -> None:
        assert vendored_paths.VendoredPaths(("vendor", "ext")).label("vendored") == "vendored (vendor, ext)"

    def test_first_party_label_is_plain(self) -> None:
        assert vendored_paths.VendoredPaths(("vendor",)).label("first_party") == "first-party"

    def test_an_undeclared_repo_has_one_scope_and_says_so(self) -> None:
        # "first-party" implies a second scope the reader would go hunting for.
        assert vendored_paths.VendoredPaths().label("first_party") == "whole repo"


class TestLintExclusion:
    """Whether ruff even reads a vendored tree.

    Ruff-derived counts (lint, complexity) report 0 for a tree ruff was told to
    skip. Printed as "vendored 0" that is a clean bill of health for code
    nobody measured, so the exclusion travels with the paths.
    """

    def test_a_ruff_excluded_vendored_tree_is_marked_unlinted(self, tmp_path: Path) -> None:
        root = _repo_with(
            tmp_path,
            {
                "pyproject.toml": '[tool.ruff]\nextend-exclude = ["upstream"]\n',
                "upstream/core.py": "x = 1\n",
            },
        )
        resolved = vendored_paths.resolve(root)
        assert resolved.unlinted == ("upstream",)
        assert resolved.fully_unlinted is True

    def test_a_vendored_tree_ruff_does_lint_is_not_marked(self, tmp_path: Path) -> None:
        root = _repo_with(
            tmp_path,
            {
                ".gitattributes": "upstream/** linguist-vendored\n",
                "pyproject.toml": "[tool.ruff]\nline-length = 120\n",
                "upstream/core.py": "x = 1\n",
            },
        )
        resolved = vendored_paths.resolve(root)
        assert resolved.unlinted == ()
        assert resolved.fully_unlinted is False

    def test_an_exclusion_covering_only_part_of_the_set_is_not_full(self, tmp_path: Path) -> None:
        root = _repo_with(
            tmp_path,
            {
                "pyproject.toml": '[tool.ruff]\nextend-exclude = ["upstream"]\n',
                "upstream/core.py": "x = 1\n",
                "external/dep.py": "y = 2\n",
            },
        )
        resolved = vendored_paths.resolve(root, ["upstream", "external"])
        assert resolved.unlinted == ("upstream",)
        assert resolved.fully_unlinted is False

    def test_an_undeclared_repo_is_never_fully_unlinted(self) -> None:
        assert vendored_paths.VendoredPaths().fully_unlinted is False


class TestSplitNote:
    def test_the_note_names_both_scopes(self) -> None:
        assert vendored_paths.VendoredPaths(("vendor",)).split_note(3, 7) == " — first-party 3, vendored 7"

    def test_an_undeclared_repo_gets_no_note(self) -> None:
        # One scope named twice would invent a second one.
        assert vendored_paths.VendoredPaths().split_note(3, 0) == ""


class TestRoundTrip:
    def test_json_report_rebuilds_the_same_value(self) -> None:
        original = vendored_paths.VendoredPaths(("vendor",), "ruff exclude (pyproject.toml)", ("vendor",))
        assert vendored_paths.from_report(original.as_dict()) == original

    def test_an_older_report_without_the_lint_status_still_loads(self) -> None:
        rebuilt = vendored_paths.from_report({"paths": ["vendor"], "source": "--vendored"})
        assert rebuilt.unlinted == ()
